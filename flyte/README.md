# Flyte

## Setup

Install the workflow requirements, create a `config.yaml` file at `~/.flyte/config.yaml` and then verify your connection to `flyte.k3s`.

```bash
pip install -r requirements.txt
pyflyte get launchplan
#                         LaunchPlans for flytesnacks/development
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
# ┃                                 Name ┃                Version ┃    State ┃ Schedule ┃
# ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
# │                 train.train_workflow │ QdmM1uId62n7vrq3LEI9yg │ INACTIVE │     None │
# ...
```

This table might be empty if you haven't launched a workflow yet.

## Run Training Workflow

To run the training workflow, use the following command:

```bash
# run <script> <workflow function name>
pyflyte run --remote flyte/train.py train_workflow
# Running Execution on Remote.
# 0:00:00 Running execution on remote.
# [✔] Go to https://flyte.k3s/console/projects/flytesnacks/domains/development/executions/<workflow-version> to see execution in the console.
```

## Observe Workflow

You can observe the workflow execution through the Flyte console. Navigate to the Flyte console URL provided by your Flyte deployment and monitor the status of your workflows.

![flyte-tasks](https://github.com/user-attachments/assets/61883829-e03f-422d-8c3a-2270e145adeb)

> A snapshot of the tasks created by [`train.py`](train.py) in http://flyte.k3s

If Loki has been configured, selecting the task view for the `train_model` task should show `Grafanamaster` as a link, which should allow you to get a live preview of the logs for each worker in the distributed run. The log output will look something like this:

```txt
[flytekit] Getting s3://flyte/flytesnacks/development/BT4G25O6GD2ZAGLE5PDHXWIT2U======/fast2e76439426f469ff0cf8e8bdc57045e5.tar.gz to ./
[flytekit] Download data to local from s3://flyte/flytesnacks/development/BT4G25O6GD2ZAGLE5PDHXWIT2U======/fast2e76439426f469ff0cf8e8bdc57045e5.tar.gz. [Time: 0.564960s]
[flytekit] Download distribution. [Time: 0.604419s]
[flytekit] Welcome to Flyte! Version: 1.14.3
[flytekit] Using user directory /tmp/flyte-ep8sczce/sandbox/local_flytekit/4b5068cdb726002df9173c5321cd361c
[flytekit] Load task. [Time: 5.690117s]
[flytekit] Getting s3://flyte/metadata/propeller/flytesnacks-development-awhp7qjnpppqw8q9j8fx/n1/data/inputs.pb to /tmp/flytebddzo0gy/local_flytekit/inputs.pb
[flytekit] Download data to local from s3://flyte/metadata/propeller/flytesnacks-development-awhp7qjnpppqw8q9j8fx/n1/data/inputs.pb. [Time: 0.287351s]
[flytekit] AsyncTranslate literal to python value. [Time: 0.000016s]
[flytekit] Translate literal to python value. [Time: 0.001440s]
[flytekit] Invoking train.train_model with inputs: {'batch_size': 64, 'epochs': 3, 'data_dir': /tmp/flytebddzo0gy/local_flytekit/9d1101326675c83e0dd5aee9adfb41d1, 'dataloader_num_workers': 2}
```

This is the initial startup logs. After it downloads the dataset and model, you'll see the distributed training initialize:

```txt
Using 16bit Automatic Mixed Precision (AMP)
GPU available: True (cuda), used: True
TPU available: False, using: 0 TPU cores
HPU available: False, using: 0 HPUs
Initializing distributed: GLOBAL_RANK: 0, MEMBER: 1/1
----------------------------------------------------------------------------------------------------
distributed_backend=gloo
All distributed processes registered. Starting with 1 processes
----------------------------------------------------------------------------------------------------
Downloading https://www.cs.toronto.edu/~kriz/cifar-100-python.tar.gz to /tmp/flytebddzo0gy/local_flytekit/9d1101326675c83e0dd5aee9adfb41d1/cifar-100-python.tar.gz
0%|          | 0/169001437 [00:00<?, ?it/s]
...
100%|██████████| 169001437/169001437 [00:08<00:00, 19030795.36it/s]
Extracting /tmp/flytebddzo0gy/local_flytekit/9d1101326675c83e0dd5aee9adfb41d1/cifar-100-python.tar.gz to /tmp/flytebddzo0gy/local_flytekit/9d1101326675c83e0dd5aee9adfb41d1
LOCAL_RANK: 0 - CUDA_VISIBLE_DEVICES: [0]
┏━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━┓
┃   ┃ Name  ┃ Type   ┃ Params ┃ Mode  ┃
┡━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━┩
│ 0 │ model │ ResNet │ 23.7 M │ train │
└───┴───────┴────────┴────────┴───────┘
Trainable params: 23.7 M
Non-trainable params: 0
Total params: 23.7 M
Total estimated model params size (MB): 94
Modules in train mode: 151
Modules in eval mode: 0
[flytekit] Starting epoch 1/3
```

You will notice that after that the epoch progress doesn't print until it reaches 100%. I have tried to prevent this from happening but have failed. For whatever reason when I switch from regular torch to lightning the progress output becomes buffered despite `PYTHON_UNBUFFERED=1`.

## Rerun Workflow with New Hyperparameters

Selecting the `Relaunch` button, or by selecting `Launch Workflow` from the `train.train_workflow` workflow in the `Workflows` tab you can launch a new workflow with different inputs. If you want to modify the code and run it remotely, use the `pyflyte` command above to launch the workflow with your latest changes.
