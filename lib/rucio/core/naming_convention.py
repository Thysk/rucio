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

from re import compile, error, match
from traceback import format_exc
from typing import TYPE_CHECKING, Any, Optional, cast

from dogpile.cache.api import NO_VALUE
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError

from rucio.common.cache import MemcacheRegion
from rucio.common.exception import Duplicate, InvalidObject, RucioException
from rucio.db.sqla import models
from rucio.db.sqla.constants import KeyType
from rucio.db.sqla.session import read_session, transactional_session

if TYPE_CHECKING:
    from typing import TypedDict

    from sqlalchemy.orm import Session

    from rucio.common.types import InternalScope

    class NamingConventionDict(TypedDict):
        scope: InternalScope
        regexp: str

REGION = MemcacheRegion(expiration_time=900)


@transactional_session
def add_naming_convention(
    scope: "InternalScope",
    regexp: str,
    convention_type: KeyType,
    *,
    session: "Session"
) -> None:
    """
    add a naming convention for a given scope

    :param scope: the name for the scope.
    :param regexp: the regular expression to validate the name.
    :param convention_type: the did_type on which the regexp should apply.
    :param session: The database session in use.
    """
    # validate the regular expression
    try:
        compile(regexp)
    except error:
        raise RucioException('Invalid regular expression %s!' % regexp)

    new_convention = models.NamingConvention(scope=scope,
                                             regexp=regexp,
                                             convention_type=convention_type)
    try:
        new_convention.save(session=session)
    except IntegrityError:
        raise Duplicate('Naming convention already exists!')
    except Exception:
        raise RucioException(str(format_exc()))


@read_session
def get_naming_convention(
    scope: "InternalScope",
    convention_type: KeyType,
    *,
    session: "Session"
) -> Optional[str]:
    """
    Get the naming convention for a given scope

    :param scope: the name for the scope.
    :param convention_type: the did_type on which the regexp should apply.
    :param session: The database session in use.

    :returns: the regular expression.
    """
    stmt = select(
        models.NamingConvention.regexp
    ).where(
        and_(models.NamingConvention.scope == scope,
             models.NamingConvention.convention_type == convention_type)
    )
    return session.execute(stmt).scalar()


@transactional_session
def delete_naming_convention(
    scope: "InternalScope",
    convention_type: KeyType,
    *,
    session: "Session"
) -> int:
    """
    delete a naming convention for a given scope

    :param scope: the name for the scope.
    :param regexp: the regular expression to validate the name. (DEPRECATED)
    :param convention_type: the did_type on which the regexp should apply.
    :param session: The database session in use.
    """
    if scope.internal is not None:
        REGION.delete(scope.internal)
    stmt = delete(
        models.NamingConvention
    ).where(
        and_(models.NamingConvention.scope == scope,
             models.NamingConvention.convention_type == convention_type)
    )
    return session.execute(stmt).rowcount


@read_session
def list_naming_conventions(*, session: "Session") -> list["NamingConventionDict"]:
    """
    List all naming conventions.

    :param session: The database session in use.

    :returns: a list of dictionaries.
    """
    stmt = select(
        models.NamingConvention.scope,
        models.NamingConvention.regexp
    )
    return [cast("NamingConventionDict", row._asdict()) for row in session.execute(stmt).all()]


@read_session
def validate_name(
    scope: "InternalScope",
    name: str,
    did_type: str,
    *,
    session: "Session"
) -> Optional[dict[str, Any]]:
    """
    Validate a name according to a naming convention.

    :param scope: the name for the scope.
    :param name: the name.
    :param did_type: the type of did.

    :param session: The database session in use.

    :returns: a dictionary with metadata.
    """
    if scope.external is not None:
        if scope.external.startswith('user'):
            return {'project': 'user'}
        elif scope.external.startswith('group'):
            return {'project': 'group'}

    # Check if naming convention can be found in cache region
    regexp = REGION.get(scope.internal)
    if regexp is NO_VALUE:  # no cached entry found
        regexp = get_naming_convention(scope=scope,
                                       convention_type=KeyType.DATASET,
                                       session=session)
        if scope.internal is not None:
            regexp and REGION.set(scope.internal, regexp)

    if not regexp:
        return

    # Validate with regexp
    groups = match(regexp, str(name))  # type: ignore
    if groups:
        meta = groups.groupdict()
        # Hack to get task_id from version
        if 'version' in meta and meta['version']:
            matched = match(r'(?P<version>\w+)_tid(?P<task_id>\d+)_\w+$', meta['version'])
            if matched:
                meta['version'] = matched.groupdict()['version']
                meta['task_id'] = int(matched.groupdict()['task_id'])
        if 'run_number' in meta and meta['run_number']:
            meta['run_number'] = int(meta['run_number'])
        return meta

    print(f"Provided name {name} doesn't match the naming convention {regexp}")
    raise InvalidObject(f"Provided name {name} doesn't match the naming convention {regexp}")
