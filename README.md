

<img src="./static/scienceboard_badge_v0.png" alt="overview" style="zoom:80%;" />

[![arXiv](https://img.shields.io/badge/arXiv-2505.19897-b31b1b.svg)](https://arxiv.org/abs/2505.19897) 
![License](https://img.shields.io/badge/License-MIT-blue)
[![Paper page](https://huggingface.co/datasets/huggingface/badges/resolve/main/paper-page-sm.svg)](https://huggingface.co/papers/2505.19897)
[![Discord](https://img.shields.io/discord/1222168244673314847?logo=discord&style=flat)](https://discord.com/invite/rXS2XbgfaD)
[![🌐 Website](https://img.shields.io/badge/Website-🌐-informational)](https://qiushisun.github.io/ScienceBoard-Home/)

Code, environment and data for "ScienceBoard: Evaluating Multimodal Autonomous Agents in Realistic Scientific Workflows"


## 🗞️ Updates
- **2025-06-08**: ScienceBoard will be presented at [WCUA@ICML 2025](https://www.icml-computeruseagents.com/) as an oral paper. 🚀
- **2025-06-04**: We release the [virtual machine snapshot](https://huggingface.co/OS-Copilot/ScienceBoard-Env) of ScienceBoard.
- **2025-05-27**: Initial release of our [paper](https://arxiv.org/abs/2505.19897), environment, benchmark, and [🌐 Project Website](https://qiushisun.github.io/ScienceBoard-Home/). Check it out! 🚀


## 🛠️ Usage
### 📦 Installation
The infrastructure of the framework is based on [OSWorld](https://github.com/xlang-ai/OSWorld) together with VMware Workstation Pro (which is free for personal use since May, 2024) in Ubuntu or Windows. Please make sure that your device meets the minimal requirements of these preliminaries.

1. Download [VMware Workstation Pro 17](https://support.broadcom.com/group/ecx/productdownloads?subfamily=VMware%20Workstation%20Pro&freeDownloads=true) and our pre-made images from [Hugging Face](https://huggingface.co/OS-Copilot/ScienceBoard-Env/blob/main/VM.zip);
2. Clone this repository and install packages needed:

    ```shell
    git clone https://github.com/OS-Copilot/ScienceBoard
    cd ScienceBoard
    conda create -n sci python=3.11
    conda activate sci
    pip install -r requirements.txt
    ```

3. We recommend you to change evaluating process in [`main.py`](main.py) directly with some sensitive information hidden in environment variables, especially when it comes to complicate configs concerning [`community`](sci/base/community.py?plain=1#L232).

> [!NOTE]  
> [`Community`](sci/base/community.py?plain=1#L16) specifies the form of cooperation in which one or more models completes the tasks. You can customize your own multi-agents system by creating a new class inheriting `Community` together with the method of `__call__()`.

### ⚙️ Env Config
#### 🔐 As a storage location for sensitive info
1. Used in our template of [`main.py`](main.py):
    - `VM_PATH`: path to vmware .vmx file; will be automatically extracted (repeatedly) if set to path of `VM.zip`
    - `HTTPX_PROXY`: proxy URL if needed; avoid clashes with `HTTP_PROXY` and `HTTPS_PROXY` on Linux;
    - `OPENAI_API_KEY`: API key for OpenAI GPT;
    - `GOOGLE_API_KEY`: API key for Google Gemini;
    - `ANTHROPIC_API_KEY`: API key for Anthropic Claude;

    and variables for open-source models:

    |   Model   |    Base URL     |       Name       |
    | :-------: | :-------------: | :--------------: |
    |  QwenVL   |  `QWEN_VL_URL`  |  `QWEN_VL_NAME`  |
    | InternVL  | `INTERN_VL_URL` | `INTERN_VL_NAME` |
    |    QVQ    |  `QVQ_VL_URL`   |  `QVQ_VL_NAME`   |
    | OS-Atlas  |  `OS_ACT_URL`   |  `OS_ACT_NAME`   |
    | GUI-Actor | `GUI_ACTOR_URL` | `GUI_ACTOR_NAME` |
    |  UI-Tars  | `TARS_DPO_URL`  | `TARS_DPO_NAME`  |

2. Used in [`sci/Presets.py`](sci/Presets.py):
    - `LEAN_LIB_PATH`: path for Lean 4 REPL;
    - `QT6_LIB_PATH`: dynamic library directory for Qt6;
    - `FFI_LIB_PATH`: dynamic library file for libffi.so;
    - `KALG_BIN_PATH`: executable binary file of KAlgebra;
    - `CELE_BIN_PATH`: executable binary file of Celestia;
    - `GIS_BIN_PATH`: executable binary file of Grass GIS.

> [!CAUTION]
> Configs defined in `sci/Presets.py` are only used for debugging under `Raw` settings and would not be loaded unless being used.

#### 🧪 As a functionality
- `DEBUG_ERR_FACT`: insert a breakpoint when eval exception occur if set to any value;

### 📏 Parameter Config
1. [`Automata`](sci/Tester.py?plain=1#L87): a simple encapsulation for [`Model`](sci/base/model.py?plain=1#L144) and [`Agent`](sci/base/agent.py?plain=1#L51)
    - `model_style`: affect the request format and response processing of model calling; you can customize your own style by adding `_request_{style}()` and `_access_{style}()` under [`Model`](sci/base/model.py?plain=1#L144);
    - `overflow_style`: affect the way we detect overflow of token; you can customize your own style by adding `{style}()` under [`Overflow`](sci/base/agent.py?plain=1#L24);
    - `code_style`: affect the way we process code blocks when communicating with models; you can customize your own style by adding `wrap_{style}()` and `extract_{style}()` under [`CodeLike`](sci/base/prompt.py?plain=1#L84).
2. [`Tester`](sci/Tester.py?plain=1#L225): `__init__()` only register a new config. use `__call__()` for actual evaluation after init.
    - `tasks_path`: the directory or file path for json file(s) of task(s); all `*.json` files under the path specified will be recursively loaded when a directory path is provided;
    - `logs_path`: the directory path for log files and will be created automatically when not existed; the structure of the directory will be arranged according to that under `tasks_path`;
    - `community`: the way of cooperation among multiple agents; use [`AllInOne`](sci/base/community.py?plain=1#L52) for standard setting inherited from OSWorld;
    - `parallel`: (experimental) run multiple VMs at the same time in a single machine; multi-process or multi-thread are both supported;
    - `ignore`: skipped when log indicates that the task is finished (by checking the existence of `result.out`) if set to `True`; so you can re-run the same program to retry failure cases only;
    - `debug`: finish the tasks manually instead of calling models;
    - `relative`: allow VM to execute `pyautogui` codes with relative coordinates; basically used by InternVL-3.

> [!CAUTION]
> Pay attention to `/tmp/sci_board.cfg` where configs of `parallel` are stored when it is set to `True`. Abnormal exit (such as `kill`) may lead to  fatal inconsistency.

### 🚧 Possible Exceptions
1. Error when initializing:

    ```shell
    Traceback (most recent call last):
        File "/usr/lib/python3.11/site-packages/requests/models.py", line 971, in json
            return complexjson.loads(self.text, **kwargs)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/usr/lib/python3.11/json/__init__.py", line 346, in loads
            return _default_decoder.decode(s)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/usr/lib/python3.11/json/decoder.py", line 337, in decode
            obj, end = self.raw_decode(s, idx=_w(s, 0).end())
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/usr/lib/python3.11/json/decoder.py", line 355, in raw_decode
            raise JSONDecodeError("Expecting value", s, err.value) from None
        json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
    ```

    the target app has not yet been started up when trying to initialize due to insufficient performance of your device; try to assign a bigger value for 'wait' field in json files of the tasks.

2. Failed to get accessibility tree:

    ```shell
    Traceback (most recent call last):
        File "os-sci/sci/Tester.py", line 396, in __call__
            counter._pass() if task_info() else counter._fail()
                            ^^^^^^^^^^^
        File "os-sci/sci/Tester.py", line 174, in __call__
            return self.task()
                ^^^^^^^^^^^
        File "os-sci/sci/base/task.py", line 175, in _avail_wrapper
            return method(self, *args, **kwargs)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "os-sci/sci/base/task.py", line 393, in __call__
            return self.__call()
                ^^^^^^^^^^^^^
        File "os-sci/sci/base/task.py", line 381, in __call
            stop_type, stop_args = self.predict()
                                ^^^^^^^^^^^^^^
        File "os-sci/sci/base/task.py", line 175, in _avail_wrapper
            return method(self, *args, **kwargs)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "os-sci/sci/base/log.py", line 462, in record_wrapper
            return_value = method(self)
                        ^^^^^^^^^^^^
        File "os-sci/sci/base/task.py", line 316, in predict
            invalid = self._step(step_index)
                    ^^^^^^^^^^^^^^^^^^^^^^
        File "os-sci/sci/base/task.py", line 260, in _step
            observation = {
                        ^
        File "os-sci/sci/base/task.py", line 261, in <dictcomp>
            obs_type: getattr(self.manager, obs_type)()
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "os-sci/sci/vm/vmanager.py", line 152, in _env_wrapper
            return method(self, *args, **kwargs)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "os-sci/sci/base/manager.py", line 85, in _assert_wrapper
            result = method(self)
                    ^^^^^^^^^^^^
        File "os-sci/sci/vm/vmanager.py", line 278, in a11y_tree
            a11y_tree = utils.linearize(raw_a11y_tree)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "os-sci/sci/vm/utils.py", line 206, in linearize
            filtered_nodes = filter_nodes(ET.fromstring(a11y_tree), platform)
                                        ^^^^^^^^^^^^^^^^^^^^^^^^
        File "/usr/lib/python3.11/xml/etree/ElementTree.py", line 1338, in XML
            parser.feed(text)
        TypeError: a bytes-like object is required, not 'NoneType'
    ```

    fail to authenticate in newly downloaded images; input password once manually in VMWare and take a new snapshot using the same name as before and delete the former one.

3. VM is mistakenly occupied when `parallel` is set to `True`:

    ```shell
    Traceback (most recent call last):
        File "sci/Tester.py", line 353, in __traverse
            new_task = self.__load(unknown_path)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^
        File "sci/Tester.py", line 340, in __load
            manager=self.__manager(type_sort),
                    ^^^^^^^^^^^^^^^^^^^^^^^^^
        File "sci/Tester.py", line 322, in __manager
            manager = manager_class(**manager_args)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "sci/KAlgebra/kalgebra.py", line 113, in __init__
            super().__init__(*args, **kwargs)
        File "sci/vm/vmanager.py", line 74, in __init__
            self.__vmx_path()
        File "sci/vm/vmanager.py", line 206, in __vmx_path
            vmxs_cfg = self.__vmx_unify(self.__read_vmx_cfg())
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "sci/vm/vmanager.py", line 180, in __vmx_unify
            assert len([
                ^^^^^
        AssertionError: VM already in use
    ```

    the remaining config of `/tmp/sci_board.cfg` failed to be cleared automatically; try to delete it manually.

## 🧑‍💻 Development Manual
### 🧩 Introduction of New Apps
If you are willing to add new applications into ScienceBoard, please make sure that you already have a full understanding of your target application and this repository.

1. Write a plugin or implant a server in your target application revealing its inner states. Listed below is repositories of our modified applications:
    - [chimerax-states](https://github.com/ShiinaHiiragi/chimerax-states): a plugin for ChimeraX;
    - [kalgebra](https://github.com/ShiinaHiiragi/kalgebra): a recompilation copy of KAlgebra;
    - [Celestia](https://github.com/ShiinaHiiragi/Celestia): a recompilation copy of Celestia;
    - [grass-gis](https://github.com/ShiinaHiiragi/grass-gui): GUI part in Python of Grass GIS.
2. Copy [`sci/Template`](sci/Template/) and rename it to the name of your target application;
    - [`template.py`](sci/Template/template.py): direct managers for the Raw / VM application;
    - [`task.py`](sci/Template/task.py): initialization and evaluation of tasks using RESTful API with your server;
    - [`__init__.py`](sci/Template/__init__.py): change the name of `template.py`.
3. Write json files of tasks and modified VM images.

### 🖼️ Crafting VM Image from Scratch 
See [Staff Manual of VM Image](vm_config/manual.md).

### 💻 Recommended Configuration 

It is recommended to run this project with at least the following configuration:

- CPU: Intel Core i7-11700
- GPU: Integrated graphics is sufficient
- Memory: 32 GB RAM
- Storage: > 100 GB available disk space

## 🤔 FAQ
We have collected some questions from emails, Hugging Face, and WeChat communications. Please check the [FAQ](https://github.com/OS-Copilot/ScienceBoard/blob/main/faq.md) 🤖


## 📋 Citation
If you are interested in our work or find this repository / our data helpful, please consider using the following citation format when referencing our paper:

```bibtex
@article{sun2025scienceboard,
  title={ScienceBoard: Evaluating Multimodal Autonomous Agents in Realistic Scientific Workflows},
  author={Sun, Qiushi and Liu, Zhoumianze and Ma, Chang and Ding, Zichen and Xu, Fangzhi and Yin, Zhangyue and Zhao, Haiteng and Wu, Zhenyu and Cheng, Kanzhi and Liu, Zhaoyang and others},
  journal={arXiv preprint arXiv:2505.19897},
  year={2025}
}
```
