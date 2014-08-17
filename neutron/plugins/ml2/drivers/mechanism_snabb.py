# Copyright (c) 2014 OpenStack Foundation
# All Rights Reserved.
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
# @author: Rahul Mohan Rekha
# @author: Luke Gorrie
# @author: Nikolay Nikolaev

from neutron.common import constants as n_const
from neutron.extensions import portbindings
from neutron.openstack.common import log
from neutron.plugins.common import constants
from neutron.plugins.ml2 import driver_api as api

LOG = log.getLogger(__name__)


class SnabbMechanismDriver(api.MechanismDriver):

    """Mechanism Driver for Snabb NFV.

    This driver implements bind_port to assign provider VLAN networks
    to Snabb NFV. Snabb NFV is a separate networking
    implementation that forwards packets to virtual machines using its
    own vswitch (Snabb Switch) on compute nodes.
    """

    def initialize(self):
        self.vif_type = portbindings.VIF_TYPE_VHOSTUSER
        self.vif_details = {portbindings.CAP_PORT_FILTER: True}

    def bind_port(self, context):
        LOG.debug("Attempting to bind port %(port)s on network %(network)s",
                  {'port': context.current['id'],
                   'network': context.network.current['id']})
        for segment in context.network.network_segments:
            if self.check_segment(segment):
                # TODO(lukego) Support binding on a specific host based on
                # networking requirements.
                context.set_binding(segment[api.ID],
                                    self.vif_type,
                                    self.vif_details,
                                    status=n_const.PORT_STATUS_ACTIVE)
                LOG.debug("Bound using segment: %s", segment)
                return
            else:
                LOG.debug("Refusing to bind port for segment ID %(id)s, "
                          "segment %(seg)s, phys net %(physnet)s, and "
                          "network type %(nettype)s",
                          {'id': segment[api.ID],
                           'seg': segment[api.SEGMENTATION_ID],
                           'physnet': segment[api.PHYSICAL_NETWORK],
                           'nettype': segment[api.NETWORK_TYPE]})

    def check_segment(self, segment):
        """Verify a segment is valid for the SnabbSwitch MechanismDriver.

        Verify the requested segment is supported by Snabb and return True or
        False to indicate this to callers.
        """
        return segment[api.NETWORK_TYPE] == constants.TYPE_VLAN
