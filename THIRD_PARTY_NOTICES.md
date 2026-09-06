# Third-party software

CheckTokens includes the o200k_base tokenizer data and encoding definition
from [OpenAI tiktoken](https://github.com/openai/tiktoken), distributed under
the MIT License. Its license is included in `src/checktokens/data/TIKTOKEN_LICENSE`.

The standalone application bundles Python and dependencies from `uv.lock`.
Their original license files are included in the app's `Resources/licenses` directory.
Key dependencies: tiktoken (MIT), striprtf (BSD-3-Clause), python-docx (MIT),
pypdf (BSD-3-Clause), charset-normalizer (MIT), PyObjC (MIT), and lxml (BSD).
PyInstaller uses the GPL with a distribution exception for generated applications.
