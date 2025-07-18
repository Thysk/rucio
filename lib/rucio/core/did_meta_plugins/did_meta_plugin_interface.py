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

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Literal

from rucio.db.sqla.session import transactional_session

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any, Optional, Union

    from sqlalchemy.orm import Session

    from rucio.common.types import InternalScope


class DidMetaPlugin(metaclass=ABCMeta):
    """
    Interface for plugins managing metadata of DIDs
    """

    def __init__(self):
        """
        Initializes the plugin
        """
        pass

    @abstractmethod
    def get_metadata(
        self,
        scope: "InternalScope",
        name: str,
        *,
        session: "Optional[Session]" = None
    ) -> "Any":
        """
        Get data identifier metadata

        :param scope: The scope name.
        :param name: The data identifier name.
        :param session: The database session in use.
        """
        pass

    @abstractmethod
    def set_metadata(
        self,
        scope: "InternalScope",
        name: str,
        key: str,
        value: str,
        recursive: bool = False,
        *,
        session: "Optional[Session]" = None
    ) -> None:
        """
        Add metadata to data identifier.

        :param scope: The scope name.
        :param name: The data identifier name.
        :param key: the key.
        :param value: the value.
        :param did: The data identifier info.
        :param recursive: Option to propagate the metadata change to content.
        :param session: The database session in use.
        """
        pass

    @transactional_session
    def set_metadata_bulk(
        self,
        scope: "InternalScope",
        name: str,
        meta: dict[str, "Any"],
        recursive: bool = False,
        *,
        session: "Optional[Session]" = None
    ) -> None:
        """
        Add metadata to data identifier in bulk.

        :param scope: The scope name.
        :param name: The data identifier name.
        :param meta: all key-values to set.
        :type meta: dict
        :param recursive: Option to propagate the metadata change to content.
        :param session: The database session in use.
        """
        for key, value in meta.items():
            self.set_metadata(scope, name, key, value, recursive=recursive, session=session)

    @abstractmethod
    def delete_metadata(
        self,
        scope: "InternalScope",
        name: str,
        key: str,
        *,
        session: "Optional[Session]" = None
    ) -> None:
        """
        Deletes the metadata stored for the given key.

        :param scope: The scope of the DID.
        :param name: The name of the DID.
        :param key: Key of the metadata.
        :param session: The database session in use.
        """
        pass

    @abstractmethod
    def list_dids(
        self,
        scope: "InternalScope",
        filters: dict[str, "Any"],
        did_type: Literal['all', 'collection', 'dataset', 'container', 'file'] = 'collection',
        ignore_case: bool = False,
        limit: "Optional[int]" = None,
        offset: "Optional[int]" = None,
        long: bool = False,
        recursive: bool = False,
        *,
        session: "Optional[Session]" = None
    ) -> "Iterator[Union[str, dict[str, Any]]]":
        """
        Search data identifiers

        :param scope: the scope name.
        :param filters: dictionary of attributes by which the results should be filtered.
        :param did_type: the type of the DID: all(container, dataset, file), collection(dataset or container), dataset, container, file.
        :param ignore_case: ignore case distinctions.
        :param limit: limit number.
        :param offset: offset number.
        :param long: Long format option to display more information for each DID.
        :param session: The database session in use.
        :param recursive: Recursively list DIDs content.
        """
        pass

    @abstractmethod
    def manages_key(
        self,
        key: str,
        *,
        session: "Optional[Session]" = None
    ) -> bool:
        """
        Returns whether key is managed by this plugin or not.
        :param key: Key of the metadata.
        :param session: The database session in use.
        :returns (Boolean)
        """
        pass
