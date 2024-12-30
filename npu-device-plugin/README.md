# NPU Device Plugin for Kubernetes

This is a Kubernetes device plugin for Rockchip NPUs. It allows you to schedule and run workloads that require access to Rockchip NPUs on your Kubernetes cluster. It automatically does hostpath volume management at the device-level, exposing the following directories:

- `/dev` to access `/dev/dri/renderD129`
- `/proc` to access `/proc/device-tree/compatible`

Because of how [rknn-toolkit2](https://github.com/airockchip/rknn-toolkit2) is written, it needs access to `compatible` to assess whether the rockchip device is supported, however, this requires a privilege level above what is normally allowed in Kubernetes.

If you are using any rknn-toolkit by airockchip, you will need to ensure the following is set in your container configuration:

```yaml
securityContext:
  privileged: true
```

## Building the Plugin

To build the plugin locally, ensure that Go v1.23 is installed on your system.

```sh
# export GOPATH=$PWD
go mod init device-plugin
go mod tidy
go install
```

Afterwards, a binary will be built at `npu-device-plugin/bin/device-plugin`

### Docker

To build the device plugin using Docker, you need to install the buildx if you are using a device that is not an arm system. Run the following command to build the Docker image:

```sh
docker buildx build --platform=arm64 -f npu-device-plugin/Dockerfile -t npu-device-plugin:latest .
# docker tag ..
# docker push ..
```

## Deploying the Plugin

Update the `daemonset.yaml` file to use your Docker image and then apply it:

```sh
kubectl apply -f npu-device-plugin/daemonset.yaml
```

This will deploy the device plugin on all nodes labeled with `node-type: npu`.

## Validation

To verify that the device plugin is working first ensure there are no logs printed in the device-plugin pods, then you can run a test job:

```sh
kubectl apply -f test.yaml
kubectl logs <pod-name>
# W Query dynamic range failed. Ret code: RKNN_ERR_MODEL_INVALID. (If it is a static shape RKNN model, please ignore the above warning message.)
# --> Load RKNN model
# done
# --> Init runtime environment
# done
# --> Running model
# resnet18
# -----TOP 5-----
# [812] score:0.999676 class:"space shuttle"
# [404] score:0.000249 class:"airliner"
# [657] score:0.000014 class:"missile"
# [833] score:0.000009 class:"submarine, pigboat, sub, U-boat"
# [466] score:0.000009 class:"bullet train, bullet"

# done
# I RKNN: [17:15:56.503] RKNN Runtime Information, librknnrt version: 1.6.0 (9a7b5d24c@2023-12-13T17:31:11)
# I RKNN: [17:15:56.503] RKNN Driver Information, version: 0.9.2
# I RKNN: [17:15:56.503] RKNN Model Information, version: 6, toolkit version: 1.6.0+81f21f4d(compiler version: 1.6.0 (585b3edcf@2023-12-11T07:42:56)), target: RKNPU v2, target platform: rk3588, framework name: PyTorch, framework layout: NCHW, model inference type: static_shape
# W RKNN: [17:15:56.523] query RKNN_QUERY_INPUT_DYNAMIC_RANGE error, rknn model is static shape type, please export rknn with dynamic_shapes
```
