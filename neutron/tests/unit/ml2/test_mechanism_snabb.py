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
# @author: Nikolay Nikolaev
# @author: Luke Gorrie

from netaddr import IPAddress
from neutron.extensions import portbindings
from neutron.plugins.common import constants
from neutron.plugins.ml2 import config as config
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers import mechanism_snabb
from neutron.tests.unit import test_db_plugin as test_plugin

PLUGIN_NAME = 'neutron.plugins.ml2.plugin.Ml2Plugin'


class SnabbTestCase(test_plugin.NeutronDbPluginV2TestCase):

    def setUp(self):
        # Enable the test mechanism driver to ensure that
        # we can successfully call through to all mechanism
        # driver apis.
        config.cfg.CONF.set_override('mechanism_drivers',
                                     ['logger', 'snabb'],
                                     'ml2')
        super(SnabbTestCase, self).setUp(PLUGIN_NAME)
        self.port_create_status = 'DOWN'
        self.segment = {'api.NETWORK_TYPE': ""}
        self.mech = mechanism_snabb.SnabbMechanismDriver()
        self.mech.vif_type = portbindings.VIF_TYPE_VHOSTUSER
        self.mech.allocated_bandwidth = None

    def test_check_segment(self):
        """Validate the check_segment call."""
        self.segment[api.NETWORK_TYPE] = constants.TYPE_LOCAL
        self.assertFalse(self.mech.check_segment(self.segment))
        self.segment[api.NETWORK_TYPE] = constants.TYPE_FLAT
        self.assertFalse(self.mech.check_segment(self.segment))
        self.segment[api.NETWORK_TYPE] = constants.TYPE_VLAN
        self.assertFalse(self.mech.check_segment(self.segment))
        self.segment[api.NETWORK_TYPE] = constants.TYPE_GRE
        self.assertFalse(self.mech.check_segment(self.segment))
        self.segment[api.NETWORK_TYPE] = constants.TYPE_VXLAN
        self.assertFalse(self.mech.check_segment(self.segment))
        self.segment[api.NETWORK_TYPE] = 'zone'
        self.assertTrue(self.mech.check_segment(self.segment))
        # Validate a network type not currently supported
        self.segment[api.NETWORK_TYPE] = 'mpls'
        self.assertFalse(self.mech.check_segment(self.segment))

class SnabbMechanismTestZone(SnabbTestCase):

    def test_choose_port_any(self):
        """Pick any port when they are all equally good."""
        self.mech.networks = {'host1': {'port0': {}, 'port1': {}, 'port2': {}}}
        self.mech.allocated_bandwidth = {}
        port = self.mech._choose_port('host1', 5)
        self.assertIsNotNone(port, 'port0')

    def test_choose_port_loaded(self):
        """Pick the most loaded port that has capacity available."""
        self.mech.networks = {'host1': {'port0': {}, 'port1': {}, 'port2': {}}}
        self.mech.allocated_bandwidth = {('host1', 'port0'): {'p1': 0},
                                         ('host1', 'port1'): {'p2': 1},
                                         ('host1', 'port2'): {'p3': 0}}
        port = self.mech._choose_port('host1', 5)
        self.assertEqual(port, 'port1')

    def test_choose_port_not_overloaded(self):
        """Don't pick the port that will be overloaded."""
        self.mech.networks = {'host1': {'port0': {}, 'port1': {}, 'port2': {}}}
        self.mech.allocated_bandwidth = {('host1', 'port0'): {'p1': 1},
                                         ('host1', 'port1'): {'p2': 6},
                                         ('host1', 'port1'): {'p2': 0}}
        port = self.mech._choose_port('host1', 5)
        self.assertNotEqual(port, 'port1')

    def test_choose_least_overloaded(self):
        """Pick the least-overloaded port."""
        self.mech.networks = {'host1': {'port0': {}, 'port1': {}, 'port2': {}}}
        self.mech.allocated_bandwidth = {('host1', 'port0'): {'p1': 99},
                                         ('host1', 'port1'): {'p2': 42},
                                         ('host1', 'port2'): {'p3': 76}}
        port = self.mech._choose_port('host1', 5)
        self.assertEqual(port, 'port1')

class SnabbMechanismTestBasicGet(test_plugin.TestBasicGet, SnabbTestCase):
    pass


class SnabbMechanismTestNetworksV2(test_plugin.TestNetworksV2, SnabbTestCase):
    pass


class SnabbMechanismTestPortsV2(test_plugin.TestPortsV2, SnabbTestCase):
    pass


class FakePlugin(object):
    """To generate plug for testing purposes only."""

    def __init__(self, ports):
        self._ports = ports
    
    def get_ports(self, dbcontext):
        return self._ports

class FakeNetworkContext(object):
    """To generate network context for testing purposes only."""

    def __init__(self, network, segments=None, original_network=None):
        self._network = network
        self._original_network = original_network
        self._segments = segments

    @property
    def current(self):
        return self._network

    @property
    def original(self):
        return self._original_network

    @property
    def network_segments(self):
        return self._segments
    
class FakePortContext(object):
    """To generate port context for testing purposes only."""

    def __init__(self, ports, host):
        self._plugin = FakePlugin(ports)
        self._plugin_context = None
        
        network = {'id': 'network_id'}
        network_segments = [{'id':'zone_id', 
                             'network_type': 'zone'}]
        self._network_context = FakeNetworkContext(network, network_segments, network)
        self._original_port = {portbindings.PROFILE: {},
                               portbindings.VIF_DETAILS: {}}
        self._port = {'binding:host_id': host,
                      portbindings.PROFILE: {},
                      portbindings.VIF_DETAILS: {}, 
                      'fixed_ips': [{'subnet_id': 'subnet_id'}], 
                      'id': 'port_id'}
        pass

    @property
    def current(self):
        return self._port

    @property
    def original(self):
        return self._original_port

    @property
    def network(self):
        return self._network_context
    
    def set_zone_gbps_ip(self, zone, gbps, ip):
        self._network_context._segments[0]['segmentation_id'] = zone
        self._original_port[portbindings.VIF_DETAILS]['zone_gbps'] = gbps
        self._port['fixed_ips'][0]['ip_address'] = ip

    def set_binding(self, segment_id, vif_type, vif_details, status):
        self._plugin._ports.append({'id': 'port_id', portbindings.VIF_DETAILS: vif_details})

    def last_bound(self):
        return self._plugin._ports[len(self._plugin._ports)-1]

class SnabbMechanismTestZoneBind(SnabbTestCase):
    def test_bind_port_ipv6(self):
        """Bind ports."""
        context = FakePortContext([], 'host1')
        self.mech.networks = {'host1': {
                               'port0': {
                                         'zone1': (IPAddress('101::'), 101), 
                                         'zone63': (IPAddress('163::'), 163)},
                               'port1': {
                                         'zone1': (IPAddress('201::'), 201),
                                         'zone63': (IPAddress('263::'), 263)}
                              }}

        # bind 10Gbps port
        context.set_zone_gbps_ip('zone1', 10, '0::10')
        self.mech.bind_port(context)
        self.assertEqual(context.last_bound()[portbindings.VIF_DETAILS]['zone_ip'], IPAddress('101::10'))

        # bind 2.5Gbps port in same zone
        context.set_zone_gbps_ip('zone1', 2.5, '0::10')
        self.mech.bind_port(context)
        self.assertEqual(context.last_bound()[portbindings.VIF_DETAILS]['zone_ip'], IPAddress('201::10'))

        # bind 2.5Gbps port in different zone
        context.set_zone_gbps_ip('zone63', 2.5, '0::10')
        self.mech.bind_port(context)
        self.assertEqual(context.last_bound()[portbindings.VIF_DETAILS]['zone_ip'], IPAddress('263::10'))

    def test_bind_port_ipv4(self):
        """Bind ports."""
        context = FakePortContext([], 'host1')
        self.mech.networks = {'host1': {
                               'port0': {
                                         'zone1': (IPAddress('101::'), 101),
                                         'zone63': (IPAddress('163::'), 163),
                                         'zone65': (IPAddress('165::'), 165)},
                               'port1': {
                                         'zone1': (IPAddress('201::'), 201),
                                         'zone63': (IPAddress('263::'), 263),
                                         'zone65': (IPAddress('192.168.111.0'), 265)}
                              }}

        # bind 1Gbps IPv4 port
        context.set_zone_gbps_ip('zone65', 1, '0.0.0.10')
        self.mech.bind_port(context)
        self.assertEqual(context.last_bound()[portbindings.VIF_DETAILS]['zone_ip'], IPAddress('192.168.111.10'))
