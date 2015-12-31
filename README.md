# Laptop Setup

This repository represents my personal laptop setup automated with Ansible. It
is indended to be used against ArchLinux and with a Dell XPS 13 9350 (late
2015/2016).

This repository is an ongoing project and will be updated as I change my setup
around or switch machines. It was last tested on building a machine from scratch
on 2015-12-28.

### ArchLinux Installation

The follow set of commands will install the base Arch system, along with
configuring disk encryption of the root partition. Once rebooted, you will be on
your new Arch system, and from there Ansible takes over configuring the system.

```
§1. Partition the disks
sgdisk --zap-all /dev/nvme0n1
cgdisk /dev/nvme0n1
> partition layout:
> p1: EFI system, 256mb - /boot - boot, esp - vfat
> p2: rest, LVM

§2. Setup disk encryption
cryptsetup -v --cipher aes-xts-plain64 --key-size 256 -y luksFormat /dev/nvme0n1p2
cryptsetup luksOpen /dev/nvme0n1p2 lvm
pvcreate /dev/mapper/lvm
vgcreate vgcrypt /dev/mapper/lvm
lvcreate --size 8G -n swap vgcrypt
lvcreate --extents +100%FREE -n root vgcrypt
mkfs.ext4 /dev/mapper/vgcrypt-root
mkswap /dev/mapper/vgcrypt-swap
mkfs.vfat /dev/nvme0n1p1

§4. Mount the partitions
mount /dev/mapper/vgcrypt-root /mnt
mkdir /mnt/boot
mount /dev/nvme0n1p1 /mnt/boot

§5. Configure networking
> Unless DHCP already did its thing...
ip addr add 192.168.1.248/24 broadcast 192.168.1.255 dev enp0s25
ip route add default via 192.168.1.1
ip link set enp0s25 up

§6. Install the base system
curl -o /etc/pacman.d/mirrorlist "https://www.archlinux.org/mirrorlist/?country=US&protocol=http&ip_version=4&use_mirror_status=on" && perl -pi -e 's/#Server/Server/g' /etc/pacman.d/mirrorlist
pacstrap /mnt base base-devel

§7. Generate the initial fstab
genfstab -L -p /mnt >> /mnt/etc/fstab

§8. Chroot into the new install
arch-chroot /mnt /bin/bash

§9. Configure the system
echo expes > /etc/hostname
sed -i "/en_US.UTF-8/ s/# *//" /etc/locale.gen
locale-gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf
export LANG=en_US.UTF-8
ln -s /usr/share/zoneinfo/America/Los_Angeles /etc/localtime
hwclock --systohc --utc
useradd -m -g users -G wheel ken && passwd ken
passwd
pacman -S sudo openssh ansible python2-httplib2
visudo   # enable wheel
systemctl enable sshd

§10. Update /etc/mkinitcpio.conf to take into account disk encryption and LVM:

HOOKS="base udev autodetect modconf block consolefont keymap keyboard encrypt lvm2 filesystems fsck"
mkinitcpio -p linux

§11. Boot loader

cp -r /mnt/loader /boot/loader
bootctl --path=/boot install

§12. Reboot
exit
umount -R /mnt
shutdown -r now
```

### Running

Before running:

```
sudo cp setup-files/ansible-hosts /etc/ansible/hosts
> copy in ssh key, or generate new one and register it with github
eval `ssh-agent`
ssh-add
```

Now you can run ansible with:

```
sudo ansible-playbook playbook.yml
```
