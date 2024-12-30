package main

import (
	"os"

	"github.com/golang/glog"
	"github.com/kubevirt/device-plugin-manager/pkg/dpm"
)

var _ dpm.ListerInterface = &Lister{}

type Lister struct {
	ResUpdateChan chan dpm.PluginNameList
}

func NewLister() *Lister {
	return &Lister{
		ResUpdateChan: make(chan dpm.PluginNameList),
	}
}

func (l *Lister) GetResourceNamespace() string {
	err := os.MkdirAll("/var/lib/kubelet/device-plugins/rockchip.com", 0755)
	if err != nil {
		glog.Errorf("failed to create directory: %v", err)
	}
	return "rockchip.com"
}

func (l *Lister) Discover(pluginListChan chan dpm.PluginNameList) {
	for {
		select {
		case detectedPlugins := <-l.ResUpdateChan:
			pluginListChan <- detectedPlugins
		case <-pluginListChan:
			return
		}
	}
}

func (l *Lister) NewPlugin(name string) dpm.PluginInterface {
	return &Plugin{}
}
