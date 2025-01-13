# Flyte

## Setup

Install the workflow requirements, create a `config.yaml` file and then verify your connection to `flyte.local`.

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
# [✔] Go to https://flyte.local/console/projects/flytesnacks/domains/development/executions/<workflow-version> to see execution in the console.
```

## Observe Workflow

You can observe the workflow execution through the Flyte console. Navigate to the Flyte console URL provided by your Flyte deployment and monitor the status of your workflows.

![flyte-tasks](https://github.com/user-attachments/assets/61883829-e03f-422d-8c3a-2270e145adeb)

> A snapshot of the tasks created by [`train.py`](train.py) in http://flyte.local

If Loki has been configured, selecting the task view for the `train_model` task should show `Grafanamaster` as a link, which should allow you to get a live preview of the logs for each worker in the distributed run.

## Rerun Workflow with New Hyperparameters

Selecting the `Relaunch` button, or by selecting `Launch Workflow` from the `train.train_workflow` workflow in the `Workflows` tab you can launch a new workflow with different inputs. If you want to modify the code and run it remotely, use the `pyflyte` command above to launch the workflow with your latest changes.
