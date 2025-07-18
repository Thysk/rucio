# Copyright European Organization for Nuclear Research (CERN) since 2012
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import TYPE_CHECKING, Any

from rucio.common.constants import DEFAULT_VO
from rucio.common.types import InternalScope
from rucio.common.utils import gateway_update_return_dict
from rucio.core import lock
from rucio.core.rse import get_rse_id
from rucio.db.sqla.constants import DatabaseOperationType, DIDType
from rucio.db.sqla.session import db_session

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


LOGGER = logging.getLogger('lock')
LOGGER.setLevel(logging.DEBUG)


def get_dataset_locks(
    scope: str,
    name: str,
    vo: str = DEFAULT_VO,
) -> 'Iterator[dict[str, Any]]':
    """
    Get the dataset locks of a dataset.

    :param scope:          Scope of the dataset.
    :param name:           Name of the dataset.
    :param vo:             The VO to act on.
    :return:               List of dicts {'rse_id': ..., 'state': ...}
    """

    internal_scope = InternalScope(scope, vo=vo)

    with db_session(DatabaseOperationType.READ) as session:
        locks = lock.get_dataset_locks(scope=internal_scope, name=name, session=session)

        for lock_object in locks:
            yield gateway_update_return_dict(lock_object, session=session)


def get_dataset_locks_bulk(
    dids: 'Iterable[dict[str, Any]]',
    vo: str = DEFAULT_VO,
) -> 'Iterator[dict[str, Any]]':
    """
    Get the dataset locks for multiple datasets or containers.

    :param dids:            List of dataset or container DIDs as dictionaries {"scope":..., "name":..., "type":...}
                            "type" is optional. If present, will be either DIDType.DATASET or DIDType.CONTAINER,
                            or string "dataset" or "container"
    :param vo:              The VO to act on.
    :return:                Generator of dicts describing found locks {'rse_id': ..., 'state': ...}. Duplicates are removed
    """

    if vo is None:
        vo = DEFAULT_VO

    dids_converted = []
    for did_in in dids:
        did = did_in.copy()
        if isinstance(did.get("type"), str):
            # convert DID type
            try:
                did["type"] = {
                    "dataset": DIDType.DATASET,
                    "container": DIDType.CONTAINER
                }[did["type"]]
            except KeyError:
                raise ValueError("Unknown DID type %(type)s" % did)
        if isinstance(did["scope"], str):
            did["scope"] = InternalScope(did["scope"], vo=vo)
        dids_converted.append(did)

    seen = set()

    with db_session(DatabaseOperationType.READ) as session:
        for lock_info in lock.get_dataset_locks_bulk(dids_converted, session=session):
            # filter duplicates - same scope, name, rse_id, rule_id
            scope_str = str(lock_info["scope"])
            key = (scope_str, lock_info["name"], lock_info["rse_id"], lock_info["rule_id"])
            if key not in seen:
                seen.add(key)
                yield lock_info


def get_dataset_locks_by_rse(
    rse: str,
    vo: str = DEFAULT_VO,
) -> 'Iterator[dict[str, Any]]':
    """
    Get the dataset locks of an RSE.

    :param rse:            RSE name.
    :param vo:             The VO to act on.
    :return:               List of dicts {'rse_id': ..., 'state': ...}
    """

    with db_session(DatabaseOperationType.READ) as session:
        rse_id = get_rse_id(rse=rse, vo=vo, session=session)
        locks = lock.get_dataset_locks_by_rse_id(rse_id=rse_id, session=session)

        for lock_object in locks:
            yield gateway_update_return_dict(lock_object, session=session)


def get_replica_locks_for_rule_id(
    rule_id: str,
    vo: str = DEFAULT_VO,
) -> 'Iterator[dict[str, Any]]':
    """
    Get the replica locks for a rule_id.

    :param rule_id:     Rule ID.
    :param vo:          The VO to act on.
    :return:            List of dicts.
    """

    with db_session(DatabaseOperationType.READ) as session:
        locks = lock.get_replica_locks_for_rule_id(rule_id=rule_id, session=session)

        for lock_object in locks:
            if lock_object['scope'].vo != vo:  # rule is on a different VO, so don't return any locks
                LOGGER.debug('rule id %s is not present on VO %s' % (rule_id, vo))
                break
            yield gateway_update_return_dict(lock_object, session=session)
