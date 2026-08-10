package main

import (
	"os"

	"github.com/golang/glog"
	"github.com/kubevirt/device-plugin-manager/pkg/dpm"
)

func main() {
	defer glog.Flush()

	lister := NewLister()
	manager := dpm.NewManager(lister)

	driverVersion, err := GetDriverVersion()
	if err != nil {
		glog.Errorf("failed to get driver version: %v", err)
		manager.Run()
		return
	}

	platform, err := GetHardwarePlatform()
	if err != nil {
		glog.Errorf("failed to get hardware platform: %v", err)
		manager.Run()
		return
	}

	glog.Infof("NPU driver version: %s", driverVersion)
	glog.Infof("Hardware platform: %s", platform)

	go func() {
		if _, err := os.Stat(devicePath); os.IsNotExist(err) {
			glog.Errorf("NPU device not found: %s", devicePath)
			return
		}

		lister.ResUpdateChan <- dpm.PluginNameList{"npu"}
	}()

	manager.Run()
}
