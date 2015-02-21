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

import netaddr

from neutron.common import constants as n_const
from neutron.common import exceptions as exc
from neutron.extensions import portbindings
from neutron.openstack.common import log
from neutron.plugins.ml2 import driver_api as api

from oslo.config import cfg

LOG = log.getLogger(__name__)

snabb_opts = [
    cfg.StrOpt('zone_definition_file',
               default='',
               help=_("File containing <host>|<port>|<zone>|<vlan>|<subnet> "
                      "tuples defining all physical ports used for zones."))
]

cfg.CONF.register_opts(snabb_opts, "ml2_snabb")

# Assume 10G network ports.
PORT_GBPS = 10

# Default bandwidth reservation (Gbps) when not specified.
DEFAULT_GBPS_ALLOCATION = 1.0


class SnabbMechanismDriver(api.MechanismDriver):

    """Mechanism Driver for Snabb NFV.

    This driver implements bind_port to assign provider VLAN networks
    to Snabb NFV. Snabb NFV is a separate networking
    implementation that forwards packets to virtual machines using its
    own vswitch (Snabb Switch) on compute nodes.
    """

    def initialize(self):
        self.vif_type = portbindings.VIF_TYPE_VHOSTUSER
        # Dictionary of {host_id: {port_id: {zone: (subnet, vlan)}}}
        #
        # Use cases:
        #   Given a host_id, find all physical ports.
        #   Given a host_id and port_id, find all valid zone networks.
        #   Given a host_id and port_id and zone, find the subnet and vlan.
        self.networks = self._load_zones()
        # Dictionary of {(host_id, port_name): gbps_currently_allocated}
        self.allocated_bandwidth = None

    def _load_zones(self):
        zonefile = cfg.CONF.ml2_snabb.zone_definition_file
        networks = {}
        if zonefile != '':
            with open(zonefile, 'rU') as f:
                for entry in f:
                    entry = entry.strip()
                    LOG.debug("zone file entry: %s", entry)
                    try:
                        host, port, zone, vlan, subnet = entry.split('|')
                        host = host.strip()
                        port = port.strip()
                        zone = int(zone)
                        vlan = int(vlan)
                        subnet = netaddr.IPAddress(subnet)
                        networks.setdefault(host, {})
                        networks[host].setdefault(port, {})
                        networks[host][port][zone] = (subnet, vlan)
                        LOG.debug("Loaded zone host:%s port:%s "
                                  "zone:%s subnet:%s vlan:%s",
                                  host, port, zone, subnet, vlan)
                    except ValueError:
                        LOG.error("Bad zone entry: %s", entry)
        return networks

    def _choose_port(self, host_id, zone, ip_version, gbps):
        """Choose the most suitable port for a new bandwidth allocation."""
        LOG.debug("Choosing port for %s gbps on host %s",
                  gbps, host_id)
        # Port that best fits, and how many gbps it has available.
        avail_ports = self.networks[host_id]
        ports = {}
        for port_id,zones in avail_ports.items():
            for name,value in zones.items():
                if name == zone and value[0].version == ip_version:
                    ports[port_id] = zones 
        assert not ports is None
        port = self._select_port_with_bandwidth(gbps, ports, host_id)
        if port is None:
            LOG.info("No port has bandwidth available. "
                     "Choosing least-overloaded.")
            port = self._select_port_least_overloaded(ports, host_id)
        LOG.info("Selected port %s.", port)
        return port

    def _select_port_with_bandwidth(self, gbps, ports, host_id):
        """Return a port with sufficient bandwidth, or None."""
        best_fit, best_fit_avail = None, None
        for port_id, _ in ports.items():
            allocated = self._get_allocated_bandwidth(host_id, port_id)
            avail = PORT_GBPS - allocated
            # Check for a best (tightest) fit
            if avail >= gbps and (best_fit == None or avail < best_fit_avail):
                best_fit, best_fit_avail = port_id, avail
        return best_fit

    def _select_port_least_overloaded(self, ports, host_id):
        """Return the last-overloaded port."""
        best_fit, best_fit_allocated = None, None
        for port_id, _ in ports.items():
            allocated = self._get_allocated_bandwidth(host_id, port_id)
            # Check for a best (least loaded) fit
            if best_fit is None or allocated < best_fit_allocated:
                best_fit, best_fit_allocated = port_id, allocated
        return best_fit

    def bind_port(self, context):
        """Bind a Neutron port to a suitable physical port.

        The port binding process includes these steps:
        1. Ensure that we know how bandwidth is currently assigned to ports.
        2. Choose a suitable physical port based on bandwidth supply/demand.
        3. Choose subnet and VLAN-ID based on physical port and zone value.
        4. Store all relevant decisions in binding:vif_details.
        5. Bind the port with VIF_VHOSTUSER to suit the Snabb Switch agent.
        """
        LOG.debug("Attempting to bind port %(port)s on network %(network)s "
                  "with profile %(profile)s",
                  {'port': context.current['id'],
                   'network': context.network.current['id'],
                   'profile': context.original[portbindings.PROFILE]})
        self._update_allocated_bandwidth(context)
        # REVISIT(lukego) Why is binding:profile set in
        # context.original but {} in context.current?
        gbps = self._requested_gbps(context.original)
        for segment in context.network.network_segments:
            if self.check_segment(segment):
                db_port_id = context.current['id']
                host_id = context.current['binding:host_id']
                zone = segment[api.SEGMENTATION_ID]
                base_ip = self._assigned_ip(context.current)
                if base_ip is None:
                    msg = "fixed_ips address required to bind zone port."
                    raise exc.InvalidInput(error_message=msg)
                base_ip = netaddr.IPAddress(base_ip)
                port_id = self._choose_port(host_id, zone, base_ip.version, gbps)
                # Calculate the correct IP address
                try:
                    subnet, vlan = self.networks[host_id][port_id][zone]
                except KeyError:
                    msg = ("zone %s not found for host:%s port:%s" %
                           (zone, host_id, port_id))
                    raise exc.InvalidInput(error_message=msg)

                if base_ip.version is 6:
                    addr_mask = netaddr.IPAddress('::ffff:ffff:ffff:ffff')
                else:
                    addr_mask = netaddr.IPAddress('0.0.0.255')
                vm_ip = (base_ip & addr_mask) | subnet
                # Store all decisions in the port vif_details.
                vif_details = {portbindings.CAP_PORT_FILTER: True,
                               'zone_host': host_id,
                               'zone_ip': vm_ip,
                               'zone_vlan': vlan,
                               'zone_port': port_id,
                               'zone_gbps': gbps}
                self._allocate_bandwidth(host_id, port_id, db_port_id, gbps)
                context.set_binding(segment[api.ID],
                                    self.vif_type,
                                    vif_details,
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

    def _requested_gbps(self, port):
        """Return the number of gbps to be reserved for port."""
        gbps = (port[portbindings.PROFILE].get('zone_gbps') or
                port[portbindings.VIF_DETAILS].get('zone_gbps') or
                DEFAULT_GBPS_ALLOCATION)
        return float(gbps)

    def _assigned_ip(self, port):
        """Return the IP address assigned to Port."""
        for ip in port['fixed_ips']:
            if ip['ip_address']:
                return ip['ip_address']

    def _get_allocated_bandwidth(self, host_id, port_id):
        """Return the amount of bandwidth allocated on a physical port."""
        allocations = self.allocated_bandwidth.get((host_id, port_id), {})
        return sum(allocations.values())

    def _allocate_bandwidth(self, host_id, port_id, neutron_port_id, gbps):
        """Record a physical bandwidth allocation."""
        self.allocated_bandwidth.setdefault((host_id, port_id), {})
        self.allocated_bandwidth[(host_id, port_id)][neutron_port_id] = gbps

    def _update_allocated_bandwidth(self, context):
        """Ensure that self.allocated_bandwidth is up-to-date."""
        # TODO(lukego) Find a reliable way to cache this information.
        self._scan_bandwidth_allocations(context)

    def _scan_bandwidth_allocations(self, context):
        """Learn bandwidth allocations by scanning all port bindings."""
        self.allocated_bandwidth = {}
        LOG.debug("context = %s", context)
        dbcontext = context._plugin_context
        ports = context._plugin.get_ports(dbcontext)
        for port in ports:
            self._scan_port_bandwidth_allocation(port)

    def _scan_port_bandwidth_allocation(self, port):
        """Learn the physical bandwdith allocated to a Neutron port."""
        details = port[portbindings.VIF_DETAILS]
        hostname = details.get('zone_host')
        portname = details.get('zone_port')
        gbps = details.get('zone_gbps')
        if hostname and portname and gbps:
            LOG.debug("Port %(port_id)s: %(gbps)s Gbps bandwidth reserved on "
                      "host %(host)s port %(port)s",
                      {'port_id': port['id'],
                       'gbps': gbps,
                       'host': hostname,
                       'port': portname})
            self._allocate_bandwidth(hostname, portname, port['id'], gbps)
        else:
            LOG.debug("Port %s: no bandwidth reservation", portname)

    def check_segment(self, segment):
        """Verify a segment is valid for the SnabbSwitch MechanismDriver.

        Verify the requested segment is supported by Snabb and return True or
        False to indicate this to callers.
        """
        return segment[api.NETWORK_TYPE] == 'zone'

