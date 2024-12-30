// E1230 06:19:47.280964       1 plugin.go:157] npu: Registration failed: rpc error: code = Unknown desc = the ResourceName "rockchip.com/npu/npu" is invalid
// E1230 06:19:47.281548       1 plugin.go:158] npu: Make sure that the DevicePlugins feature gate is enabled and kubelet running
// E1230 06:19:47.281705       1 manager.go:214] Failed to start plugin's "npu" server, atempt 1 ouf of 3 waiting 3000000000 before next try: rpc error: code = Unknown desc = the ResourceName "rockchip.com/npu/npu" is invalid
// E1230 06:19:50.287632       1 plugin.go:157] npu: Registration failed: rpc error: code = Unknown desc = the ResourceName "rockchip.com/npu/npu" is invalid
// E1230 06:19:50.287723       1 plugin.go:158] npu: Make sure that the DevicePlugins feature gate is enabled and kubelet running
// E1230 06:19:50.288379       1 manager.go:214] Failed to start plugin's "npu" server, atempt 2 ouf of 3 waiting 3000000000 before next try: rpc error: code = Unknown desc = the ResourceName "rockchip.com/npu/npu" is invalid
// E1230 06:19:53.293948       1 plugin.go:157] npu: Registration failed: rpc error: code = Unknown desc = the ResourceName "rockchip.com/npu/npu" is invalid
// E1230 06:19:53.294058       1 plugin.go:158] npu: Make sure that the DevicePlugins feature gate is enabled and kubelet running
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
