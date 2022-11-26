# Debian dual-boot setup

* Two Debian sid installed
* Each with their own physical LUKS partition
* Each with their own /boot
* A shared EFI system partition is mounted to /boot/efi
* Different entry tokens are configured in /etc/kernel/entry-token
* The kernel command-line options are configured in /etc/kernel/cmdline,
  including the root=UUID=<root fs UUID> option
* When a new kernel is installed:
 1. The kernel in /boot is updated to the one just installed
 2. The initramfs in /boot is updated. It configures the root filesystem
    to be used during boot according to the /etc/cryptfs and /etc/fstab
    entries.
 3. /etc/kernel/postinst.d/zz-systemd-boot is executed, which executes
    kernel-install:
    * The entry token is read from /etc/kernel/entry-token
    * The kernel command-line options are read from /etc/kernel/cmdline
    * /usr/lib/kernel/install.d/90-loaderentry.install is exucuted, which:
      * copies kernel and initramfs from /boot to /boot/efi/<entry token>/
      * creates a systemd boot entry in /boot/efi/loader/entries/

