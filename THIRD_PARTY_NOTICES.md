# Third-party software

CheckTokens includes the o200k_base tokenizer data and encoding definition
from [OpenAI tiktoken](https://github.com/openai/tiktoken), distributed under
the MIT License. Its license is included in `src/checktokens/data/TIKTOKEN_LICENSE`.

The standalone application bundles Python and dependencies from `uv.lock`.
Their original license files are included in the macOS app's `Resources/licenses`
directory or the Windows app's `_internal/licenses` directory.
Key dependencies: tiktoken (MIT), striprtf (BSD-3-Clause), python-docx (MIT),
pypdf (BSD-3-Clause), charset-normalizer (MIT), PyObjC (MIT, macOS), lxml (BSD),
and PySide6/Qt/Shiboken (LGPL-3.0, Windows).
The Windows package dynamically loads unmodified Qt libraries and Python bindings
from PySide6-Essentials 6.11.2 and shiboken6 6.11.2. Their license texts and third-party
notices are included under `_internal/licenses`. Corresponding source is available
from the upstream [Qt for Python repository](https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.11.2)
and [Qt Base repository](https://code.qt.io/cgit/qt/qtbase.git/?h=v6.11.2).
These libraries remain replaceable as separate DLL/PYD files; CheckTokens itself
is MIT-licensed. System fonts are used at runtime and are not redistributed.
Windows builds made with LLVM-MinGW also include the toolchain's license notices
for the statically linked C++ runtime in `_internal/licenses/llvm-mingw`.
PyInstaller uses the GPL with a distribution exception for generated applications.
