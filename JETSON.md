# Nvidia Jetson Orin NX 8GB

Here is my flashing experience with the Jetson Orin SOCM board. Since I lack a waveshare dev board to flash the Orin properly you're going to get to see why there is a white lie in the first lines of the [documentation](https://docs.turingpi.com/docs/nvidia-jetson-orin-nx-intro-specs) for this product.

> *"The whole installation process might not be quick but should be pretty straightforward. In the future, we hope to make it much easier."*

## Flashing

The flashing process can be broken down into several steps.

1. Connect the Jetson eMMC Storage to your PC
2. Pass that device to an Ubuntu 22.04 Installation on your PC
3. Manually Flash from that VM to the Jetson
4. Install all of the relevant Drivers and Software Packages for CUDA

You might be asking yourself a few questions like, why is the software installation included in the flashing process? Why do you need a linux VM? Why can't you just use the BMC to flash the Jetson?

You can't just flash the Jetson with the BMC unfortunately, because of how Nvidia designed the Jetson. The USB connection from the Turing Pi isn't recognizable by the Jetson and Turing Pi hasn't figured out how to hack it yet, so instead of flashing it with the BMC the Jetson has to be flashed by another Linux System. Why another Linux System? Because that's what the community has figured out.

The only process certified by Nvidia for the Jetson is using the Waveshare dev board, and unless you went shell out another $120 for a board you're only going to use once, and only works on that specific series of Jetson (meaning if I got a Jetson Super I'd have to get a new waveshare board).

Finally, the entire process is very specific. Because we're using an unsupported board for the Jetson, we have to manually modify some of the driver package files. More on that later.

### USB

I spent more than a week just trying to connect the board to my PC. The first sign that things were going wrong was that it wasn't clear which USB port was the correct port for flashing the Jetson, and the instructions don't tell you to put the device in `flash` mode, but instead in `device` mode.

Furthermore, the order of operations is very specific, and I didn't expect this at first:

```sh
tpi power off -n 4
tpi usb device -n 4
tpi power on -n 4
```

After connecting the cable, I noticed that a USB device appeared, but it had an error `Port Reset Failed`. Furthermore, depending on the order of operations you used to connect the device, it wouldn't even show up most of the time. Sometimes it would take 10+ minutes for the device to show up with the same error. This problem took a long time to solve and eventually I realized a few things:

- There are 3 USB Ports, and the Vertical one is for Flashing ONLY through node 1
- There are 3 USB-C Ports, and the one next to the Veritcal USB-A Port is for Flashing any Node
- You have to use a USB 3.0 Cable (Blue Tab)
- Despite what the documentation says, you have to use `flash` mode to put the Jetson module into maskROM mode to expose the M.2 device connected to that node

### WSL & USBIPD

The tutorial for this recommends using VMWare Player, and while it can work out of the box on up to date Windows 11 Systems I prefer using WSL for this process. It's faster and easier to use. This didn't end up working, but I have hopes that one day it will. I installed a new Ubuntu 22.04 VM and configured the BSP & Sample Root Filesystem. It took a long time to extract the files and multiple attempts just to get `./apply_binaries.sh` to work. Because the Jetpack version I was using was much higher than the one written on the docs, the bootloader directory is different.

```sh
# From
sed -i 's/cvb_eeprom_read_size = <0x100>/cvb_eeprom_read_size = <0x0>/g' Linux_for_Tegra/bootloader/t186ref/BCT/tegra234-mb2-bct-misc-p3767-0000.dts

# To
sed -i 's/cvb_eeprom_read_size = <0x100>/cvb_eeprom_read_size = <0x0>/g' Linux_for_Tegra/bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts
```

I just searched for the `.dts` file using `find . -name '*.dts' | grep p3767` and saw that a single directory was changed.

Afterwards, I installed [usbipd](https://github.com/dorssel/usbipd-win) to share usb devices between windows and WSL. I could also stop using Windows Device Manager in favor of Powershell and `usbipd list`. When I tried to bind the usb device however, I received a generic error, indicating that the device wasn't ready.

### VMWare Player

Eventually I just switched over to using VMWare Player because the biggest issue I had run into thus far was just getting the device to connect, and I wanted to use a method that was at least tested and documented. The setup process went smoothly and all I can really say is that it was very slow. Furthermore, I had to re-download and setup the BSP & Sample Root Filesystem because there isn't really an easy storage passthrough on the VMWare Player. There probably is one, but I didn't find it.

After eventually figuring out the cable issue, I was able to connect the Turing Pi the VMWare Player, and flash the OS to the NVMe drive and get it to boot properly. It takes a few attempts to do this, and in my case all I had to do was move the SOCM from slot 3 to 4.

## SDKManager

After flashing the OS, I neglected to use the SDKManager originally. I couldn't get it to run off of the node or on Windows native, and instead opted to just install the cuda packages manually. This was a big mistake, and I ended up having to uninstall an hours worth of installing packages. There's a checkpoint that you run to verify that cuda is working with docker and containerd with something like `docker run --rm --runtime nvidia xift/jetson_devicequery:r32.5.0`.

At first, I thought that it was just because the jetpack version that I'm using isn't supported, but I ended up finding that deviceQuery file and running it locally to the same error. No matter how I installed CUDA and it's supporting libraries I couldn't find the ARM version of some packages publicly and simultaneously couldn't get `jtop` to show the versions for all of the required software. I was going to have to go back to the SDKManager to install everything again.

I made a huge mistake once I booted up the VMWare Player again and launched a fresh installation of the SDKManager. I accidentally let it flash my Jetson. This bricked it immediately as the flash installation failed. I realized late into the process and had to re-run the above steps again.

Remember how I mentioned that it took me a few attempts to flash the Jetson manually? This is also true for the software installation. I estimate that I did 4-5 attempts of just running the software installation before I realized that it isn't going to work, and switch the SOCM from slot 4 to 3. Only 2 attempts later did it complete successfully. This installation process took a solid 6 hours to run on my VM, and I modified the default CPU/Memory that it used.

I ran deviceQuery again and it succeeded. All that pain for 1 GPU.

## ISCSI

My journey with the Jetson wasn't over, after adding it to the cluster I was able to make use of the GPU just fine. I found a wonderful repository of [Jetson Container](https://github.com/dusty-nv/jetson-containers) and started working on the [Jetson Exporter](/jetson-exporter/README.md). However when I tried to setup Open-WebUI I ran into an issue. Longhorn, the storage provider I'm using was failing to attach a volume to the PVC I wanted to create for Ollama.

The main goal of having a PVC for Ollama was to have persistence for the models that are downloaded. If Ollama is restarted it could just load models that were already stored. This was my first attempt at actually using a PVC on my Jetson node and I realized that something was wrong. No PVCs could be attached on that node and it left the PVC indefinetly in `Pending`.

An installation step that wasn't covered by the documentation that had to be run was installing `open-iscsi` and `nfs-common`. This allows Longhorn to create network storage and attach to nodes over TCP.

I started troubleshooting on the node and found that the iscsi service never actually started and furthermore, wasn't supported according to its journal entry. Furthermore, I saw that the `csi-attacher` wasn't working on the jetson node. I also used `./longhornctl check preflight --kube-config ~/.kube/config` with `Failed to run preflight checker: open /host/boot/config-5.15.148-tegra: no such file or directory` and found the same. This indicated that storage could be provisioned on the Jetson, just not attached to it.

Unfortunately, this meant that I had to recompile the tegra linux kernel to enable the `iscsi_over_tcp` module.

I've never actually compiled the linux kernel before. I wasn't sure what the approach was, but eventually I found that all we needed to do was compile the module file, copy it to the expected location, and change the `.config` file that indicates that the module is installed. This meant that I didn't need to do this process in the VMWare Player and then redo the entire flashing process, which would be very painful. I found the BSP Sources which contained the kernel and opened them up locally on the jetson.

![BSP Sources](https://github.com/user-attachments/assets/882f6e4f-ffaf-4b4e-ae19-c963e05a9507)
> The BSP Sources contain the tegra kernel

Since this isn't documented well anywhere else, here's the steps I took to add the module from start to finish:

```sh
# Step 1: Download and extract the NVIDIA public sources
wget https://developer.nvidia.com/downloads/embedded/l4t/r36_release_v4.0/sources/public_sources.tbz2
tar -xjf public_sources.tbz2
cd Linux_for_Tegra/source/

# Step 2: Extract the kernel source
cp kernel_src.tbz2 ../
cd ..
tar -xjf kernel_src.tbz2
cd kernel/kernel-*-src/

# Step 3: Configure environment variables for cross-compilation
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-

# Step 4: Load the default kernel configuration for Tegra
zcat /proc/config.gz > .config          # Start with the current kernel configuration
make olddefconfig                       # Update the configuration to match the current tool versions

# Step 5: Set `-tegra` in EXTRAVERSION
# Validate or edit `EXTRAVERSION` in the Makefile
grep "EXTRAVERSION" Makefile            # Check the current `EXTRAVERSION` value
nano Makefile                           # Ensure `EXTRAVERSION = -tegra` is set
                                        # OR
make menuconfig                         # Go to `General Setup -> Local version`
                                        # Set `-tegra` here manually if needed.

# Step 6: Enable iSCSI support in the kernel configuration
make menuconfig                         # Open the kernel configuration editor
                                        # Navigate to `Device Drivers -> SCSI device support -> iSCSI transport attributes`
                                        # Enable `CONFIG_ISCSI_TCP=m` for iSCSI over TCP as a module

# Step 7: Build the entire kernel (this step is mandatory to properly initialize symbols, headers, etc.)
make -j$(nproc)                         # Compile the entire kernel
                                        # This ensures that any interdependencies in the kernel build system are resolved.
                                        # Note: This will take a while.

# Step 8: Install the kernel and its modules
sudo make modules_install               # Install compiled kernel modules
sudo make install                       # Install the compiled kernel image
                                        # If you're only building the modules and not the full kernel, you can skip this.

# Step 9: Rebuild only the iSCSI module (if needed)
# Note: At this point, the `iscsi_tcp.ko` module should already exist,
# but this step ensures the module can be built standalone if needed.
make M=drivers/scsi -j$(nproc)          # Rebuild just the specific module directory

# Step 10: Verify the `iscsi_tcp.ko` module was built
find . -name iscsi_tcp.ko               # Ensure the `iscsi_tcp.ko` module file exists

# Step 11: Install the iSCSI module
sudo cp drivers/scsi/iscsi_tcp.ko /lib/modules/$(uname -r)/kernel/drivers/scsi/
sudo depmod -a                          # Refresh the module dependencies
sudo modprobe iscsi_tcp                 # Load the module into the running kernel

# Step 12: Verify the module is loaded
dmesg | tail                            # Check kernel logs for confirmation that the module loaded successfully
lsmod | grep iscsi_tcp                  # Ensure the module is listed as loaded

# Step 13: (Optional) Reboot the system (if the kernel was updated)
sudo reboot

# Step 14: Confirm success after reboot
uname -r                                # Verify the running kernel version matches expectations
lsmod | grep iscsi_tcp                  # Ensure the iscsi_tcp module is active after reboot

# Step 15: Confirm that Longhorn is happy
curl -sSfL https://raw.githubusercontent.com/longhorn/longhorn/v1.7.0/scripts/environment_check.sh | bash
```

Afterwards, I restarted all of longhorn's services and was able to attach to the jetson.
