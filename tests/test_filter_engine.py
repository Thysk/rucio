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

import operator
import unittest
from datetime import datetime, timedelta

import pytest

from rucio.common.exception import DuplicateCriteriaInDIDFilter
from rucio.common.utils import generate_uuid
from rucio.core.did import add_did
from rucio.core.did_meta_plugins import set_metadata
from rucio.core.did_meta_plugins.filter_engine import FilterEngine
from rucio.db.sqla import models
from rucio.db.sqla.util import json_implemented


class TestFilterEngineDummy:
    def test_input_sanitisation(self):
        filters = FilterEngine('  TestKeyword1  =  True  ,  TestKeyword2   =   0; 1 < TestKeyword4 <= 2', strict_coerce=False).filters
        filters_expected = [[('TestKeyword1', operator.eq, 1),
                             ('TestKeyword2', operator.eq, 0)],
                            [('TestKeyword4', operator.gt, 1),
                            ('TestKeyword4', operator.le, 2)]]
        assert filters == filters_expected

        with pytest.raises(ValueError):
            FilterEngine('did_type >= 1', strict_coerce=False)

        with pytest.raises(ValueError):
            FilterEngine('name >= 1', strict_coerce=False)

        with pytest.raises(ValueError):
            FilterEngine('length >= test', strict_coerce=False)

        with pytest.raises(ValueError):
            FilterEngine('name >= *', strict_coerce=False)

    def test_operators_equal_not_equal(self):
        assert FilterEngine('True = True', strict_coerce=False).evaluate()
        assert FilterEngine('True != False', strict_coerce=False).evaluate()

    def test_one_sided_inequality(self):
        assert FilterEngine('1 < 2', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2', strict_coerce=False).evaluate()
        assert FilterEngine('1 <= 1', strict_coerce=False).evaluate()
        assert FilterEngine('1 >= 1', strict_coerce=False).evaluate()

    def test_compound_inequality(self):
        assert FilterEngine('3 > 2 > 1', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2 > 3', strict_coerce=False).evaluate()
        with pytest.raises(DuplicateCriteriaInDIDFilter):
            FilterEngine('1 < 2 > 3', strict_coerce=False)
        with pytest.raises(DuplicateCriteriaInDIDFilter):
            FilterEngine('1 < 2 > 3', strict_coerce=False)

    def test_and_groups(self):
        assert FilterEngine('True = True, False = False', strict_coerce=False).evaluate()
        assert not FilterEngine('True = True, False = True', strict_coerce=False).evaluate()
        assert FilterEngine('3 > 2, 2 > 1', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2, 2 > 1', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2, 2 > 3', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2, 4 > 3 > 2', strict_coerce=False).evaluate()

    def test_or_groups(self):
        assert FilterEngine('True = True; True = True', strict_coerce=False).evaluate()
        assert FilterEngine('True = True; True = False', strict_coerce=False).evaluate()
        assert not FilterEngine('True = False; False = True', strict_coerce=False).evaluate()
        assert FilterEngine('3 > 2; 2 > 1', strict_coerce=False).evaluate()
        assert FilterEngine('1 > 2; 2 > 1', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2; 2 > 3', strict_coerce=False).evaluate()
        assert FilterEngine('1 > 2; 4 > 3 > 2', strict_coerce=False).evaluate()

    def test_and_or_groups(self):
        assert FilterEngine('1 > 2, 4 > 3 > 2; True=True', strict_coerce=False).evaluate()
        assert not FilterEngine('1 > 2, 4 > 3 > 2; True=False', strict_coerce=False).evaluate()

    def test_backwards_compatibility_created_after(self):
        test_expressions = {
            "created_after=1900-01-01 00:00:00": [[('created_at', operator.ge, datetime(1900, 1, 1, 0, 0))]],
            "created_after=1900-01-01T00:00:00": [[('created_at', operator.ge, datetime(1900, 1, 1, 0, 0))]],
            "created_after=1900-01-01 00:00:00.000Z": [[('created_at', operator.ge, datetime(1900, 1, 1, 0, 0))]],
            "created_after=1900-01-01T00:00:00.000Z": [[('created_at', operator.ge, datetime(1900, 1, 1, 0, 0))]]
        }
        for input_datetime_expression, filters_expected in test_expressions.items():
            filters = FilterEngine(input_datetime_expression, strict_coerce=False).filters
            assert filters == filters_expected

    def test_backwards_compatibility_created_before(self):
        test_expressions = {
            "created_before=1900-01-01 00:00:00": [[('created_at', operator.le, datetime(1900, 1, 1, 0, 0))]],
            "created_before=1900-01-01T00:00:00": [[('created_at', operator.le, datetime(1900, 1, 1, 0, 0))]],
            "created_before=1900-01-01 00:00:00.000Z": [[('created_at', operator.le, datetime(1900, 1, 1, 0, 0))]],
            "created_before=1900-01-01T00:00:00.000Z": [[('created_at', operator.le, datetime(1900, 1, 1, 0, 0))]]
        }
        for input_datetime_expression, filters_expected in test_expressions.items():
            filters = FilterEngine(input_datetime_expression, strict_coerce=False).filters
            assert filters == filters_expected

    def test_backwards_compatibility_length(self):
        test_expressions = {
            'length > 0': [[('length', operator.gt, 0)]],
            'length < 0': [[('length', operator.lt, 0)]],
            'length >= 0': [[('length', operator.ge, 0)]],
            'length <= 0': [[('length', operator.le, 0)]],
            'length == 0': [[('length', operator.eq, 0)]]
        }
        for input_length_expression, filters_expected in test_expressions.items():
            filters = FilterEngine(input_length_expression, strict_coerce=False).filters
            assert filters == filters_expected

    def test_typecast_string(self):
        test_expressions = {
            'testkeyint1 = 0': int,
            'testkeyfloat1 = 0.5': float,
            'testkeystr1 = test': str,
            'testbool1 = false': bool,
            'testbool2 = False': bool,
            'testbool3 = FALSE': bool,
            'testbool4 = true': bool,
            'testbool5 = True': bool,
            'testbool6 = TRUE': bool,
            'testkeydate1 = 1900-01-01 00:00:00': datetime,
            'testkeydate2 = 1900-01-01 00:00:00.000Z': datetime,
            'testkeydate3 = 1900-01-01T00:00:00': datetime,
            'testkeydate4 = 1900-01-01T00:00:00.000Z': datetime
        }
        for input_length_expression, type_expected in test_expressions.items():
            filters = FilterEngine(input_length_expression, strict_coerce=False).filters
            assert isinstance(filters[0][0][2], type_expected)


class TestFilterEngineReal:

    def _create_tmp_did(self, scope, account, did_type='DATASET'):
        did_name = 'fe_test_did_%s' % generate_uuid()
        add_did(scope=scope, name=did_name, did_type=did_type, account=account)
        return did_name

    def test_operators_equal_not_equal(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name1 = self._create_tmp_did(mock_scope, root_account)
        did_name2 = self._create_tmp_did(mock_scope, root_account)
        did_name3 = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name1, key='run_number', value=1)
        set_metadata(scope=mock_scope, name=did_name2, key='run_number', value=2)

        dids = []
        stmt = FilterEngine('run_number=1', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)

        dids = []
        stmt = FilterEngine('run_number!=1', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 3 (NULL counted in not equals)
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name1 = self._create_tmp_did(mock_scope, root_account)
            did_name2 = self._create_tmp_did(mock_scope, root_account)
            did_name3 = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name1, key='testkeyint1', value=1)
            set_metadata(scope=mock_scope, name=did_name2, key='testkeyint2', value=2)
            set_metadata(scope=mock_scope, name=did_name3, key='testkeyint3', value=2)

            dids = []
            stmt = FilterEngine('testkeyint1=1', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)

        if json_implemented(session=db_session):
            dids = []
            stmt = FilterEngine('testkeyint1!=1', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 0 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)

    def test_one_sided_inequality(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name, key='run_number', value=1)

        dids = []
        stmt = FilterEngine('run_number > 0', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('run_number < 2', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('run_number < 0', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 != list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('run_number > 2', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 != list(map(lambda did: did.name == did_name, dids)).count(True)
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name, key='testkeyint1', value=1)

            dids = []
            stmt = FilterEngine('testkeyint1 > 0', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

            dids = []
            stmt = FilterEngine('testkeyint1 < 2', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

            dids = []
            stmt = FilterEngine('testkeyint1 < 0', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 != list(map(lambda did: did.name == did_name, dids)).count(True)

            dids = []
            stmt = FilterEngine('testkeyint1 > 2', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 != list(map(lambda did: did.name == did_name, dids)).count(True)

    def test_compound_inequality(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name, key='run_number', value=1)

        dids = []
        stmt = FilterEngine('0 < run_number < 2', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('0 < run_number <= 1', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('0 <= run_number < 1', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 != list(map(lambda did: did.name == did_name, dids)).count(True)
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name, key='testkeyint1', value=1)

            dids = []
            stmt = FilterEngine('0 < testkeyint1 < 2', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

            dids = []
            stmt = FilterEngine('0 < testkeyint1 <= 1', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

            dids = []
            stmt = FilterEngine('0 <= testkeyint1 < 1', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 != list(map(lambda did: did.name == did_name, dids)).count(True)

    def test_and_groups(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name1 = self._create_tmp_did(mock_scope, root_account)
        did_name2 = self._create_tmp_did(mock_scope, root_account)
        did_name3 = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name1, key='run_number', value='1')
        set_metadata(scope=mock_scope, name=did_name2, key='project', value="test")
        set_metadata(scope=mock_scope, name=did_name3, key='run_number', value='1')
        set_metadata(scope=mock_scope, name=did_name3, key='project', value="test")

        dids = []
        stmt = FilterEngine('run_number = 1, project = test', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 3

        dids = []
        stmt = FilterEngine('run_number = 1, project != test', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name1 = self._create_tmp_did(mock_scope, root_account)
            did_name2 = self._create_tmp_did(mock_scope, root_account)
            did_name3 = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name1, key='testkeyint1', value='1')
            set_metadata(scope=mock_scope, name=did_name2, key='testkeystr1', value="test")
            set_metadata(scope=mock_scope, name=did_name3, key='testkeyint1', value='1')
            set_metadata(scope=mock_scope, name=did_name3, key='testkeystr1', value="test")

            dids = []
            stmt = FilterEngine('testkeyint1 = 1, testkeystr1 = test', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 3

            dids = []
            stmt = FilterEngine('testkeyint1 = 1, testkeystr1 != test', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 0 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)

    def test_or_groups(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name1 = self._create_tmp_did(mock_scope, root_account)
        did_name2 = self._create_tmp_did(mock_scope, root_account)
        did_name3 = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name1, key='run_number', value='1')
        set_metadata(scope=mock_scope, name=did_name2, key='project', value="test")
        set_metadata(scope=mock_scope, name=did_name3, key='run_number', value='1')
        set_metadata(scope=mock_scope, name=did_name3, key='project', value="test")

        dids = []
        stmt = FilterEngine('run_number = 1; project = test', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 3 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 2, 3

        dids = []
        stmt = FilterEngine('run_number = 1; project != test', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 3

        dids = []
        stmt = FilterEngine('run_number = 0; run_number = 1', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 3

        dids = []
        stmt = FilterEngine('run_number = 0; run_number = 3', model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 0 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)

        dids = []
        stmt = FilterEngine('name = {}; name = {}; name = {}'.format(did_name1, did_name2, did_name3), model_class=models.DataIdentifier).create_sqla_query(
            additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 3 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 2, 3
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name1 = self._create_tmp_did(mock_scope, root_account)
            did_name2 = self._create_tmp_did(mock_scope, root_account)
            did_name3 = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name1, key='testkeyint1', value='1')
            set_metadata(scope=mock_scope, name=did_name2, key='testkeystr1', value="test")
            set_metadata(scope=mock_scope, name=did_name3, key='testkeyint1', value='1')
            set_metadata(scope=mock_scope, name=did_name3, key='testkeystr1', value="test")

            dids = []
            stmt = FilterEngine('testkeyint1 = 1; testkeystr1 = test', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 3 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 2, 3

            dids = []
            stmt = FilterEngine('testkeyint1 = 1; testkeystr1 != test', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 3

            dids = []
            stmt = FilterEngine('testkeyint1 = 0; testkeyint1 = 1', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 3

            dids = []
            stmt = FilterEngine('testkeyint1 = 0; testkeyint1 = 3', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 0 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)

            dids = []
            stmt = FilterEngine('name = {}; name = {}; name = {}'.format(did_name1, did_name2, did_name3), model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 3 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 2, 3

    def test_and_or_groups(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name1 = self._create_tmp_did(mock_scope, root_account)
        did_name2 = self._create_tmp_did(mock_scope, root_account)
        did_name3 = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name1, key='run_number', value='1')
        set_metadata(scope=mock_scope, name=did_name2, key='project', value="test")
        set_metadata(scope=mock_scope, name=did_name3, key='run_number', value='1')
        set_metadata(scope=mock_scope, name=did_name3, key='project', value="test")

        dids = []
        stmt = FilterEngine('run_number = 1, project != test; project = test', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 3 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 1, 2, 3

        dids = []
        stmt = FilterEngine('run_number = 1, project = test; run_number != 1', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 2, 3
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name1 = self._create_tmp_did(mock_scope, root_account)
            did_name2 = self._create_tmp_did(mock_scope, root_account)
            did_name3 = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name1, key='testkeyint1', value='1')
            set_metadata(scope=mock_scope, name=did_name2, key='testkeystr1', value="test")
            set_metadata(scope=mock_scope, name=did_name3, key='testkeyint1', value='1')
            set_metadata(scope=mock_scope, name=did_name3, key='testkeystr1', value="test")

            dids = []
            stmt = FilterEngine('testkeyint1 = 1, testkeystr1 != test; testkeystr1 = test', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 2, 3

            dids = []
            stmt = FilterEngine('testkeyint1 = 1, testkeystr1 = test; testkeyint1 != 1', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3), dids)).count(True)  # 3

    def test_backwards_compatibility_created_after(self, db_session, mock_scope, root_account):
        before = datetime.strftime(datetime.utcnow() - timedelta(seconds=1), "%Y-%m-%dT%H:%M:%S.%fZ")  # w/ -1s buffer
        did_name = self._create_tmp_did(mock_scope, root_account)

        dids = []
        stmt = FilterEngine('created_after={}'.format(before), model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

    def test_backwards_compatibility_created_before(self, db_session, mock_scope, root_account):
        did_name = self._create_tmp_did(mock_scope, root_account)
        after = datetime.strftime(datetime.utcnow() + timedelta(seconds=1), "%Y-%m-%dT%H:%M:%S.%fZ")  # w/ +1s buffer

        dids = []
        stmt = FilterEngine('created_before={}'.format(after), model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

    def test_backwards_compatibility_length(self, db_session, mock_scope, root_account):
        did_name = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name, key='length', value='10')

        dids = []
        stmt = FilterEngine('length >= 10', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('length > 9', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('length <= 10', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

        dids = []
        stmt = FilterEngine('length < 11', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name == did_name, dids)).count(True)

    def test_wildcards(self, db_session, mock_scope, root_account):
        # Plugin: DID
        #
        did_name1 = self._create_tmp_did(mock_scope, root_account)
        did_name2 = self._create_tmp_did(mock_scope, root_account)
        did_name3 = self._create_tmp_did(mock_scope, root_account)
        did_name4 = self._create_tmp_did(mock_scope, root_account)
        did_name5 = self._create_tmp_did(mock_scope, root_account)
        set_metadata(scope=mock_scope, name=did_name1, key='project', value="test1")
        set_metadata(scope=mock_scope, name=did_name2, key='project', value="test2")
        set_metadata(scope=mock_scope, name=did_name3, key='project', value="anothertest1")
        set_metadata(scope=mock_scope, name=did_name4, key='project', value="anothertest2")

        dids = []
        stmt = FilterEngine('project = test*', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 1, 2

        dids = []
        stmt = FilterEngine('project = *test*', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 4 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 1, 2, 3, 4

        dids = []
        stmt = FilterEngine('project != *anothertest*', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 3 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 3, 4, 5 (NULL counted in not equals)

        dids = []
        stmt = FilterEngine('project != *test*', model_class=models.DataIdentifier).create_sqla_query(additional_model_attributes=[models.DataIdentifier.name])
        dids += [did for did in db_session.execute(stmt).yield_per(5)]
        dids = set(dids)
        assert 1 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 5 (NULL counted in not equals)
        db_session.commit()

        # Plugin: JSON
        #
        if json_implemented(session=db_session):
            did_name1 = self._create_tmp_did(mock_scope, root_account)
            did_name2 = self._create_tmp_did(mock_scope, root_account)
            did_name3 = self._create_tmp_did(mock_scope, root_account)
            did_name4 = self._create_tmp_did(mock_scope, root_account)
            did_name5 = self._create_tmp_did(mock_scope, root_account)
            set_metadata(scope=mock_scope, name=did_name1, key='testkeystr1', value="test1")
            set_metadata(scope=mock_scope, name=did_name2, key='testkeystr1', value="test2")
            set_metadata(scope=mock_scope, name=did_name3, key='testkeystr1', value="anothertest1")
            set_metadata(scope=mock_scope, name=did_name4, key='testkeystr1', value="anothertest2")

            dids = []
            stmt = FilterEngine('testkeystr1 = test*', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 1, 2

            dids = []
            stmt = FilterEngine('testkeystr1 = *test*', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                additional_model_attributes=[
                    models.DidMeta.scope,
                    models.DidMeta.name
                ],
                json_column=models.DidMeta.meta)
            dids += [did for did in db_session.execute(stmt).yield_per(5)]
            dids = set(dids)
            assert 4 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 1, 2, 3, 4

            if db_session.bind.dialect.name != 'oracle':
                dids = []
                stmt = FilterEngine('testkeystr1 != *anothertest*', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                    additional_model_attributes=[
                        models.DidMeta.scope,
                        models.DidMeta.name
                    ],
                    json_column=models.DidMeta.meta)
                dids += [did for did in db_session.execute(stmt).yield_per(5)]
                dids = set(dids)
                assert 2 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)  # 3, 4

                dids = []
                stmt = FilterEngine('testkeystr1 != *test*', model_class=models.DidMeta, strict_coerce=False).create_sqla_query(
                    additional_model_attributes=[
                        models.DidMeta.scope,
                        models.DidMeta.name
                    ],
                    json_column=models.DidMeta.meta)
                dids += [did for did in db_session.execute(stmt).yield_per(5)]
                dids = set(dids)
                assert 0 == list(map(lambda did: did.name in (did_name1, did_name2, did_name3, did_name4, did_name5), dids)).count(True)


if __name__ == '__main__':
    unittest.main()
