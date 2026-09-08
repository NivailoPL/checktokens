// A short-lived, out-of-process Explorer verb. No document parsing in Explorer.
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <shobjidl.h>
#include <shlobj.h>
#include <sddl.h>
#include <atomic>
#include <string>
#include <vector>

// Keep in sync with install-windows.ps1 and uninstall-windows.ps1.
const CLSID CLSID_CheckTokens = {0x28e4a510,0xebad,0x4b47,{0x93,0xc5,0x0a,0x85,0x11,0xa4,0xc1,0xc8}};
std::atomic<long> objects{0};
std::atomic<long> locks{0};
ULONGLONG lastActivity = 0;

struct Handle {
    HANDLE h = INVALID_HANDLE_VALUE;
    explicit Handle(HANDLE value = INVALID_HANDLE_VALUE) : h(value) {}
    ~Handle() { if (h && h != INVALID_HANDLE_VALUE) CloseHandle(h); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
};

std::wstring ownPath() {
    std::vector<wchar_t> buffer(32768);
    DWORD n = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    return std::wstring(buffer.data(), n);
}

std::string jsonString(const wchar_t* value) {
    int n = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value, -1, nullptr, 0, nullptr, nullptr);
    if (!n) return "";
    std::string utf8(n, '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value, -1, utf8.data(), n, nullptr, nullptr);
    utf8.pop_back();
    std::string result = "\"";
    const char* hex = "0123456789abcdef";
    for (unsigned char c : utf8) {
        if (c == '"' || c == '\\') { result += '\\'; result += c; }
        else if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += c;
    }
    return result + "\"";
}

bool complete(HANDLE pipe, OVERLAPPED& ov, BOOL immediate, DWORD& bytes) {
    if (!immediate && GetLastError() != ERROR_IO_PENDING) return false;
    if (!immediate && WaitForSingleObject(ov.hEvent, 30000) != WAIT_OBJECT_0) {
        CancelIoEx(pipe, &ov);
        GetOverlappedResult(pipe, &ov, &bytes, TRUE);
        return false;
    }
    return GetOverlappedResult(pipe, &ov, &bytes, FALSE) != FALSE;
}

HRESULT deliver(IShellItemArray* selection) {
    DWORD count = 0;
    HRESULT hr = selection->GetCount(&count);
    if (FAILED(hr) || !count) return E_INVALIDARG;
    std::string json = "[";
    for (DWORD i = 0; i < count; ++i) {
        IShellItem* item = nullptr;
        hr = selection->GetItemAt(i, &item);
        if (FAILED(hr)) return hr;
        PWSTR path = nullptr;
        hr = item->GetDisplayName(SIGDN_FILESYSPATH, &path);
        item->Release();
        if (FAILED(hr)) return hr;
        auto encoded = jsonString(path);
        CoTaskMemFree(path);
        if (encoded.empty()) return E_INVALIDARG;
        if (i) json += ',';
        json += encoded;
        if (json.size() > 16 * 1024 * 1024 - 1) return HRESULT_FROM_WIN32(ERROR_BUFFER_OVERFLOW);
    }
    json += ']';

    Handle token;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token.h)) return HRESULT_FROM_WIN32(GetLastError());
    DWORD required = 0;
    GetTokenInformation(token.h, TokenUser, nullptr, 0, &required);
    std::vector<BYTE> info(required);
    if (!GetTokenInformation(token.h, TokenUser, info.data(), required, &required)) return E_ACCESSDENIED;
    LPWSTR sid = nullptr;
    if (!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(info.data())->User.Sid, &sid)) return E_ACCESSDENIED;
    std::wstring sddl = L"D:P(A;;GA;;;" + std::wstring(sid) + L")";
    LocalFree(sid);
    PSECURITY_DESCRIPTOR descriptor = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.c_str(), SDDL_REVISION_1, &descriptor, nullptr)) return E_ACCESSDENIED;
    SECURITY_ATTRIBUTES security{sizeof(security), descriptor, FALSE};
    GUID id;
    CoCreateGuid(&id);
    wchar_t guid[40];
    StringFromGUID2(id, guid, 40);
    std::wstring pipeName = L"\\\\.\\pipe\\CheckTokens-" + std::wstring(guid + 1, 36);
    Handle pipe(CreateNamedPipeW(pipeName.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
        1, 65536, 65536, 30000, &security));
    LocalFree(descriptor);
    if (pipe.h == INVALID_HANDLE_VALUE) return HRESULT_FROM_WIN32(GetLastError());

    Handle event(CreateEventW(nullptr, TRUE, FALSE, nullptr));
    OVERLAPPED ov{};
    ov.hEvent = event.h;
    BOOL connected = ConnectNamedPipe(pipe.h, &ov);
    DWORD connectError = connected ? ERROR_SUCCESS : GetLastError();
    if (!connected && connectError != ERROR_IO_PENDING && connectError != ERROR_PIPE_CONNECTED) return HRESULT_FROM_WIN32(connectError);
    auto exe = ownPath();
    exe = exe.substr(0, exe.find_last_of(L"\\/") + 1) + L"CheckTokens.exe";
    std::wstring command = L"\"" + exe + L"\" --_selection-pipe \"" + pipeName + L"\"";
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(exe.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr, nullptr, &startup, &process)) {
        DWORD error = GetLastError();
        CancelIoEx(pipe.h, &ov);
        DWORD ignored;
        GetOverlappedResult(pipe.h, &ov, &ignored, TRUE);
        return HRESULT_FROM_WIN32(error);
    }
    Handle processHandle(process.hProcess), threadHandle(process.hThread);
    DWORD bytes = 0;
    if (!connected && connectError == ERROR_IO_PENDING) {
        SetLastError(ERROR_IO_PENDING);
        if (!complete(pipe.h, ov, FALSE, bytes)) return HRESULT_FROM_WIN32(ERROR_TIMEOUT);
    }
    uint32_t length = static_cast<uint32_t>(json.size());
    std::string payload(reinterpret_cast<char*>(&length), sizeof(length));
    payload += json;
    ResetEvent(event.h);
    ov = {}; ov.hEvent = event.h;
    BOOL written = WriteFile(pipe.h, payload.data(), static_cast<DWORD>(payload.size()), nullptr, &ov);
    if (!complete(pipe.h, ov, written, bytes) || bytes != payload.size()) return E_FAIL;
    ResetEvent(event.h);
    ov = {}; ov.hEvent = event.h;
    BYTE ack = 0;
    BOOL read = ReadFile(pipe.h, &ack, 1, nullptr, &ov);
    if (!complete(pipe.h, ov, read, bytes) || bytes != 1 || ack != 1) return E_FAIL;
    return S_OK;
}

class Command final : public IExecuteCommand, public IObjectWithSelection {
    std::atomic<ULONG> refs{1};
    IShellItemArray* selection = nullptr;
public:
    Command() { ++objects; }
    ~Command() { if (selection) selection->Release(); --objects; lastActivity = GetTickCount64(); }
    IFACEMETHODIMP QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid == IID_IUnknown || iid == IID_IExecuteCommand) *out = static_cast<IExecuteCommand*>(this);
        else if (iid == IID_IObjectWithSelection) *out = static_cast<IObjectWithSelection*>(this);
        else return E_NOINTERFACE;
        AddRef(); return S_OK;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return ++refs; }
    IFACEMETHODIMP_(ULONG) Release() override { ULONG n = --refs; if (!n) delete this; return n; }
    IFACEMETHODIMP SetSelection(IShellItemArray* value) override {
        if (value) value->AddRef();
        if (selection) selection->Release();
        selection = value; return S_OK;
    }
    IFACEMETHODIMP GetSelection(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        return selection ? selection->QueryInterface(iid, out) : E_FAIL;
    }
    IFACEMETHODIMP SetKeyState(DWORD) override { return S_OK; }
    IFACEMETHODIMP SetParameters(LPCWSTR) override { return S_OK; }
    IFACEMETHODIMP SetPosition(POINT) override { return S_OK; }
    IFACEMETHODIMP SetShowWindow(int) override { return S_OK; }
    IFACEMETHODIMP SetNoShowUI(BOOL) override { return S_OK; }
    IFACEMETHODIMP SetDirectory(LPCWSTR) override { return S_OK; }
    IFACEMETHODIMP Execute() override {
        HRESULT hr = selection ? deliver(selection) : E_INVALIDARG;
        if (FAILED(hr)) MessageBoxW(nullptr, L"Could not send the selected files to CheckTokens. Please try again or reinstall the application.", L"CheckTokens", MB_OK | MB_ICONERROR);
        return hr;
    }
};

class Factory final : public IClassFactory {
    std::atomic<ULONG> refs{1};
public:
    IFACEMETHODIMP QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid != IID_IUnknown && iid != IID_IClassFactory) return E_NOINTERFACE;
        *out = static_cast<IClassFactory*>(this); AddRef(); return S_OK;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return ++refs; }
    IFACEMETHODIMP_(ULONG) Release() override { ULONG n = --refs; if (!n) delete this; return n; }
    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID iid, void** out) override {
        if (outer) return CLASS_E_NOAGGREGATION;
        auto command = new Command;
        HRESULT hr = command->QueryInterface(iid, out);
        command->Release(); return hr;
    }
    IFACEMETHODIMP LockServer(BOOL value) override { locks += value ? 1 : -1; return S_OK; }
};

// Integration probe: uses the registered COM class, including marshalled selection.
HRESULT invoke(int argc, wchar_t** argv) {
    std::vector<PIDLIST_ABSOLUTE> ids;
    HRESULT hr = S_OK;
    for (int i = 2; i < argc && SUCCEEDED(hr); ++i) {
        PIDLIST_ABSOLUTE id = nullptr;
        hr = SHParseDisplayName(argv[i], nullptr, &id, 0, nullptr);
        if (SUCCEEDED(hr)) ids.push_back(id);
    }
    IShellItemArray* array = nullptr;
    if (SUCCEEDED(hr) && !ids.empty()) hr = SHCreateShellItemArrayFromIDLists(static_cast<UINT>(ids.size()), const_cast<PCIDLIST_ABSOLUTE*>(ids.data()), &array);
    else hr = E_INVALIDARG;
    for (auto id : ids) CoTaskMemFree(id);
    IObjectWithSelection* object = nullptr;
    if (SUCCEEDED(hr)) hr = CoCreateInstance(CLSID_CheckTokens, nullptr, CLSCTX_LOCAL_SERVER, IID_PPV_ARGS(&object));
    if (SUCCEEDED(hr)) hr = object->SetSelection(array);
    IExecuteCommand* command = nullptr;
    if (SUCCEEDED(hr)) hr = object->QueryInterface(IID_PPV_ARGS(&command));
    if (SUCCEEDED(hr)) hr = command->Execute();
    if (command) command->Release();
    if (object) object->Release();
    if (array) array->Release();
    return hr;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    if (FAILED(CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED))) return 1;
    int argc = 0;
    auto argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argc > 1 && std::wstring(argv[1]) == L"--invoke") {
        auto hr = invoke(argc, argv);
        LocalFree(argv); CoUninitialize(); return SUCCEEDED(hr) ? 0 : 1;
    }
    bool server = argc > 1 && (_wcsicmp(argv[1], L"-Embedding") == 0 || _wcsicmp(argv[1], L"/Embedding") == 0);
    LocalFree(argv);
    if (!server) { CoUninitialize(); return 0; }
    auto factory = new Factory;
    DWORD cookie = 0;
    HRESULT hr = CoRegisterClassObject(CLSID_CheckTokens, factory, CLSCTX_LOCAL_SERVER, REGCLS_MULTIPLEUSE, &cookie);
    factory->Release();
    if (FAILED(hr)) { CoUninitialize(); return 1; }
    lastActivity = GetTickCount64();
    UINT_PTR timer = SetTimer(nullptr, 0, 1000, nullptr);
    MSG message;
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        if (message.message == WM_TIMER && !objects && !locks && GetTickCount64() - lastActivity > 10000) break;
        TranslateMessage(&message); DispatchMessageW(&message);
    }
    KillTimer(nullptr, timer);
    CoRevokeClassObject(cookie);
    CoUninitialize();
    return 0;
}
