# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2014 OpenStack Foundation
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

"""Add QoS db models

Revision ID: 562fa8b1d4b5
Revises: 538732fa21e1
Create Date: 2013-04-22 10:53:29.669259

"""

# revision identifiers, used by Alembic.
revision = '562fa8b1d4b5'
down_revision = '538732fa21e1'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = [
    '*',
]

from neutron.common import constants
from neutron.db import migration

from alembic import op
import sqlalchemy as sa


def upgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.create_table(
        'qoses',
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('type', sa.Enum(constants.TYPE_QOS_DSCP,
                                  constants.TYPE_QOS_RATELIMIT,
                                  name='qos_types')),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'qos_policies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('qos_id', sa.String(length=36), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['qos_id'], ['qoses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', 'qos_id', 'key'),
    )

    op.create_table(
        'networkqosmappings',
        sa.Column('network_id', sa.String(length=36), nullable=False,
                  primary_key=True),
        sa.Column('qos_id', sa.String(length=36), nullable=False,
                  primary_key=True),
        sa.ForeignKeyConstraint(['network_id'], ['networks.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['qos_id'], ['qoses.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'portqosmappings',
        sa.Column('port_id', sa.String(length=36), nullable=False,
                  primary_key=True),
        sa.Column('qos_id', sa.String(length=36), nullable=False,
                  primary_key=True),
        sa.ForeignKeyConstraint(['port_id'], ['ports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['qos_id'], ['qoses.id'], ondelete='CASCADE'),
    )


def downgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.drop_table('portqosmappings')
    op.drop_table('networkqosmappings')
    op.drop_table('qos_policies')
    op.drop_table('qoses')
