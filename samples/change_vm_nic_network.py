#!/usr/bin/env python
#
# Author: Tim Cheung
# Email: tim.cheung@telefonica.com
#
# Note: Example code For testing purposes only
#
# This code has been released under the terms of the Apache-2.0 license
# http://opensource.org/licenses/Apache-2.0
#
# Description: Move Network on existing vm interface to another portgroup.
# Will only work with Distributed Virtual Switches

import atexit
from pyVmomi import vim
from pyVim.connect import SmartConnectNoSSL, Disconnect
from tools import tasks, cli


def get_args():
    parser = cli.build_arg_parser()
    parser.add_argument('-n', '--vmname', required=True,
                        help="Name of the VirtualMachine you want to change.")
    parser.add_argument('-m', '--unitnumber', required=True,
                        help='Network Inferface number.', type=int)
    parser.add_argument('-g', '--portgroup', required=True,
                        help='Name of the port group you want to change the NIC onto.')

    my_args = parser.parse_args()
    return cli.prompt_for_password(my_args)


def get_obj(content, vimtype, name):
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj


def get_portgroup_id(content, portgroup):
    portgroup_id = None
    pg_obj = get_obj(content, [vim.dvs.DistributedVirtualPortgroup], portgroup)
    portgroup_id = pg_obj.key
    dvs_uuid = pg_obj.config.distributedVirtualSwitch.uuid
    return portgroup_id, dvs_uuid


def update_virtual_nic_portgroup(si, vm_obj, nic_number, portgroup_id, dvs_uuid):
    """
    :param si: Service Instance
    :param vm_obj: Virtual Machine Object
    :param nic_number: Network Interface Controller Number
    :return: True if success
    """
    nic_prefix_label = 'Network adapter '
    nic_label = nic_prefix_label + str(nic_number)
    virtual_nic_device = None
    for dev in vm_obj.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard) \
                and dev.deviceInfo.label == nic_label:
            virtual_nic_device = dev
    if not virtual_nic_device:
        raise RuntimeError('Virtual {} could not be found.'.format(nic_label))

    virtual_nic_spec = vim.vm.device.VirtualDeviceSpec()
    virtual_nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    virtual_nic_spec.device = virtual_nic_device
    virtual_nic_spec.device.key = virtual_nic_device.key
    virtual_nic_spec.device.macAddress = virtual_nic_device.macAddress
    virtual_nic_spec.device.backing = virtual_nic_device.backing
    virtual_nic_spec.device.deviceInfo.summary = 'DVSwitch: {}'.format(dvs_uuid)
    virtual_nic_spec.device.backing.port.switchUuid = dvs_uuid
    virtual_nic_spec.device.backing.port.connectionCookie = None
    virtual_nic_spec.device.backing.port.portgroupKey = portgroup_id
    virtual_nic_spec.device.backing.port.portKey = None
    dev_changes = []
    dev_changes.append(virtual_nic_spec)
    spec = vim.vm.ConfigSpec()
    spec.deviceChange = dev_changes
    task = vm_obj.ReconfigVM_Task(spec=spec)
    tasks.wait_for_tasks(si, [task])
    return True


def main():
    args = get_args()

    # connect to vc
    si = SmartConnectNoSSL(
        host=args.host,
        user=args.user,
        pwd=args.password,
        port=args.port)
    # disconnect vc
    atexit.register(Disconnect, si)

    content = si.RetrieveContent()
    print 'Searching for VM {}'.format(args.vmname)
    vm_obj = get_obj(content, [vim.VirtualMachine], args.vmname)
    portgroup_id, dvs_uuid = get_portgroup_id(content, args.portgroup)

    if vm_obj:
        update_virtual_nic_portgroup(si, vm_obj, args.unitnumber, portgroup_id, dvs_uuid)
        print 'VM NIC {} successfully' \
              ' portgroup changed to {}'.format(args.unitnumber, args.portgroup)
    else:
        print "VM not found"

# start
if __name__ == "__main__":
    main()
