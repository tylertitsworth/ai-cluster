package main

import (
	"context"

	"github.com/golang/glog"
	"github.com/kubevirt/device-plugin-manager/pkg/dpm"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

var _ dpm.PluginInterface = &Plugin{}

type Plugin struct {
}

func (p *Plugin) GetDevicePluginOptions(ctx context.Context, e *pluginapi.Empty) (*pluginapi.DevicePluginOptions, error) {
	return &pluginapi.DevicePluginOptions{}, nil
}

func (p *Plugin) PreStartContainer(ctx context.Context, r *pluginapi.PreStartContainerRequest) (*pluginapi.PreStartContainerResponse, error) {
	return &pluginapi.PreStartContainerResponse{}, nil
}

func (p *Plugin) ListAndWatch(e *pluginapi.Empty, s pluginapi.DevicePlugin_ListAndWatchServer) error {
	devices := []*pluginapi.Device{
		{
			ID:     devicePath,
			Health: pluginapi.Healthy,
		},
	}

	err := s.Send(&pluginapi.ListAndWatchResponse{Devices: devices})
	if err != nil {
		glog.Errorf("failed to send ListAndWatch response: %v", err)
		return err
	}

	for {
		select {}
	}
}

func (p *Plugin) Allocate(ctx context.Context, r *pluginapi.AllocateRequest) (*pluginapi.AllocateResponse, error) {
	var response pluginapi.AllocateResponse

	for _, req := range r.ContainerRequests {
		car := pluginapi.ContainerAllocateResponse{}

		for _, id := range req.DevicesIDs {
			glog.Infof("Allocating device ID: %s", id)

			dev := &pluginapi.DeviceSpec{
				ContainerPath: id,
				HostPath:      id,
				Permissions:   "rw", // Read and write permissions
			}

			car.Devices = append(car.Devices, dev)
		}

		// Add `/proc/device-tree/compatible` as a mount
		mount := &pluginapi.Mount{
			ContainerPath: "/proc/device-tree/compatible", // Path in container
			HostPath:      "/proc/device-tree/compatible", // Path on the host system
			ReadOnly:      true,                           // Only need to read this file
		}
		car.Mounts = append(car.Mounts, mount)

		response.ContainerResponses = append(response.ContainerResponses, &car)
	}

	return &response, nil
}

func (p *Plugin) GetPreferredAllocation(context.Context, *pluginapi.PreferredAllocationRequest) (*pluginapi.PreferredAllocationResponse, error) {
	return &pluginapi.PreferredAllocationResponse{}, nil
}
