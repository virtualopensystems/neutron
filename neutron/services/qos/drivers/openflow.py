# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Sean M. Collins, sean@coreitpro.com, Comcast #

from neutron.common import constants
from neutron.services.qos.drivers import qos_base


class OpenflowQoSVlanDriver(qos_base.QoSDriver):
    #TODO(scollins) - refactor into dynamic calls
    # 99% of the code is identical
    def __init__(self, ext_bridge, int_bridge, local_vlan_map):
        self.ext_bridge = ext_bridge
        self.int_bridge = int_bridge
        self.local_vlan_map = local_vlan_map
        # Quick lookup table for qoses that are
        # already present - help determine if it's a create
        # or update. RPC does not distinguish between updates and creates
        self.qoses = {}

    def _create_flow_statement_for_policy(self, policy):
        action = ""
        if constants.TYPE_QOS_DSCP in policy:
            action += "mod_nw_tos=%s" % (int(policy[constants.TYPE_QOS_DSCP])
                                         << 2)
        return action

    def create_qos_for_network(self, policy, network_id):
        if network_id not in self.local_vlan_map:
            return
        vlmap = self.local_vlan_map[network_id]
        mod_nw_tos = self._create_flow_statement_for_policy(policy)
        if vlmap.segmentation_id:
            # Add another action to existing
            # flow that rewrites the VLAN tag ID
            self.ext_bridge.mod_flow(dl_vlan=vlmap.vlan,
                                     actions="mod_vlan_vid=%s,%s,NORMAL" % (
                                         vlmap.segmentation_id, mod_nw_tos)
                                     )
        else:
            # Fallback to creating a new flow
            self.ext_bridge.add_flow(dl_vlan=vlmap.vlan, actions="%s,NORMAL" %
                                     mod_nw_tos)
        self.qoses[network_id] = True

    def delete_qos_for_network(self, network_id):
        if (network_id not in self.qoses or
                network_id not in self.local_vlan_map):
            return
        vlmap = self.local_vlan_map[network_id]
        if vlmap.segmentation_id:
            # Provider network - remove the mod_nw_tos key from
            # the flow
            self.ext_bridge.mod_flow(
                dl_vlan=vlmap.vlan,
                actions="mod_vlan_vid=%s,NORMAL" % vlmap.segmentation_id)
        else:
            self.ext_bridge.delete_flows(dl_vlan=vlmap.vlan)
        del self.qoses[network_id]

    def network_qos_updated(self, policy, network_id):
        # Remove old flow, create new one with the updated policy
        self.delete_qos_for_network(network_id)
        self.create_qos_for_network(policy, network_id)

    def create_qos_for_port(self, policy, port_id):
        #TODO(scollins) - create flow statments that will
        #ensure that a port qos policy overrides the qos policy
        #of a network
        ofport = self.int_bridge.get_vif_port_by_id(port_id).ofport
        action = "%s,NORMAL" % self._create_flow_statement_for_policy(policy)
        self.int_bridge.add_flow(in_port=ofport, actions=action,
                                 priority=65535)
        self.qoses[port_id] = True

    def delete_qos_for_port(self, port_id):
        if port_id not in self.qoses:
            return
        ofport = self.int_bridge.get_vif_port_by_id(port_id).ofport
        self.int_bridge.delete_flows(in_port=ofport)
        del self.qoses[port_id]

    def port_qos_updated(self, policy, port_id):
        # Remove flow, create new one with the updated policy
        self.delete_qos_for_port(port_id)
        self.create_qos_for_port(policy, port_id)
