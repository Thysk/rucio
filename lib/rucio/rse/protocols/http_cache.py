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

from rucio.rse.protocols import ngarc


class Default(ngarc.Default):

    """ Implementing access to RSEs using the ngarc protocol."""

    def __init__(self, protocol_attr, rse_settings, logger=None):
        """ Initializes the object with information about the referred RSE.

            :param props: Properties derived from the RSE Repository
        """
        super(Default, self).__init__(protocol_attr, rse_settings, logger=logger)  # type: ignore (logger might be None)
        self.attributes.pop('determinism_type', None)
        self.files = []

    def _get_path(self, scope, name):
        """ Transforms the physical file name into the local URI in the referred RSE.
            Suitable for sites implementoing the RUCIO naming convention.

            :param name: filename
            :param scope: scope

            :returns: RSE specific URI of the physical file
        """
        return '%s/%s' % (scope, name)

    def path2pfn(self, path):
        """
            Returns a fully qualified PFN for the file referred by path.

            :param path: The path to the file.

            :returns: Fully qualified PFN.

        """
        return ''.join([self.attributes['scheme'], '://%s' % self.attributes['hostname'], path])

    def put(self, source, target, source_dir=None, transfer_timeout=None):
        """ Allows to store files inside the referred RSE.

            :param source: Physical file name
            :param target: Name of the file on the storage system e.g. with prefixed scope
            :param source_dir Path where the to be transferred files are stored in the local file system
            :param transfer_timeout Transfer timeout (in seconds)

            :raises DestinationNotAccessible, ServiceUnavailable, SourceNotFound
        """
        raise NotImplementedError

    def delete(self, pfn):
        """ Deletes a file from the connected RSE.

            :param pfn: Physical file name

            :raises ServiceUnavailable, SourceNotFound
        """
        raise NotImplementedError

    def rename(self, pfn, new_pfn):
        """ Allows to rename a file stored inside the connected RSE.

            :param pfn:      Current physical file name
            :param new_pfn  New physical file name

            :raises DestinationNotAccessible, ServiceUnavailable, SourceNotFound
        """
        raise NotImplementedError
