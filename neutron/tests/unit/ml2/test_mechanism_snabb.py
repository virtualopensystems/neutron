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
