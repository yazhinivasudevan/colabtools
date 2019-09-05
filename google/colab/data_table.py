# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Interactive table for displaying pandas dataframes.

Example:

  from google.colab.data_table import DataTable
  from vega_datasets import data
  airports = data.airports()  # DataFrame
  DataTable(airports)  # Displays as interactive table
"""
from __future__ import absolute_import as _
from __future__ import division as _
from __future__ import print_function as _

import json as _json
import traceback as _traceback
import IPython as _IPython
from IPython.utils import traitlets as _traitlets
import pandas as _pd
import six as _six

from google.colab import _interactive_table_helper

__all__ = [
    'DataTable', 'enable_dataframe_formatter', 'disable_dataframe_formatter',
    'load_ipython_extension', 'unload_ipython_extension'
]

_GVIZ_JS = 'https://ssl.gstatic.com/colaboratory/data_table/6adb00bb049ef96e/data_table.js'

_DATA_TABLE_HELP_URL = 'https://colab.research.google.com/notebooks/data_table.ipynb'

_JAVASCRIPT_MODULE_MIME_TYPE = 'application/vnd.google.colaboratory.module+javascript'

#  pylint:disable=g-import-not-at-top
#  pylint:disable=g-importing-member
if _six.PY2:
  from cgi import escape as _escape
else:
  from html import escape as _escape
#  pylint:enable=g-importing-member
#  pylint:enable=g-import-not-at-top


def _force_to_latin1(x):
  return 'nonunicode data: %s...' % _escape(x[:100].decode('latin1'))


_DEFAULT_NONUNICODE_FORMATTER = _force_to_latin1
if _six.PY2:
  _DEFAULT_FORMATTERS = {unicode: lambda x: x.encode('utf8')}
else:
  _DEFAULT_FORMATTERS = {str: lambda x: x}


class DataTable(_IPython.display.DisplayObject):
  """An interactive data table display.

  Attributes:
    include_index: (boolean) whether to include the index in a table by default.
    num_rows_per_page: (int) default number of rows per page.
    max_rows: (int) number of rows beyond which the table will be truncated.
    max_columns: (int) number of columns beyond which the table will be
      truncated.
  """
  # Configurable defaults for initialization.
  include_index = True
  num_rows_per_page = 25
  max_rows = 20000
  max_columns = 20

  @classmethod
  def formatter(cls, dataframe, **kwargs):
    # Don't use data table for hierarchical index or columns.
    if isinstance(dataframe.columns, _pd.MultiIndex):
      return None
    if isinstance(dataframe.index, _pd.MultiIndex):
      return None
    # For large dataframes, fall back to pandas rather than truncating.
    if dataframe.shape[0] > cls.max_rows:
      return None
    if dataframe.shape[1] > cls.max_columns:
      return None
    return cls(dataframe, **kwargs)._repr_javascript_module_()  # pylint: disable=protected-access

  def __init__(self,
               dataframe,
               include_index=None,
               num_rows_per_page=None,
               max_rows=None,
               max_columns=None):
    """Constructor.

    Args:
       dataframe: the dataframe source for the table
       include_index: boolean specifying whether index should be included.
         Defaults to DataTable.include_index
       num_rows_per_page: display that many rows per page initially. Defaults to
         DataTable.num_rows_per_page.
       max_rows: if len(data) exceeds this value a warning will be printed and
         the table truncated. Defaults to DataTable.max_rows.
       max_columns: if len(columns) exceeds this value a warning will be printed
         and truncated. Defaults to DataTable.max_columns.
    """

    def _default(value, default):
      return default if value is None else value

    self._dataframe = dataframe
    self._include_index = _default(include_index, self.include_index)
    self._num_rows_per_page = _default(num_rows_per_page,
                                       self.num_rows_per_page)
    self._max_rows = _default(max_rows, self.max_rows)
    self._max_columns = _default(max_columns, self.max_columns)

  def _preprocess_dataframe(self):
    dataframe = self._dataframe.iloc[:self._max_rows, :self._max_columns]

    if self._include_index or dataframe.shape[1] == 0:
      dataframe = dataframe.reset_index()
    if not dataframe.columns.is_unique:
      df_copy = dataframe.copy(deep=False)
      df_copy.columns = range(dataframe.shape[1])
      records = df_copy.to_records(index=False)
      dataframe = records[[str(n) for n in list(records.dtype.names)]]
    return dataframe

  def _repr_mimebundle_(self, include=None, exclude=None):
    mime_bundle = {'text/html': self._repr_html_()}
    try:
      dataframe = self._preprocess_dataframe()
      mime_bundle[_JAVASCRIPT_MODULE_MIME_TYPE] = self._gen_js(dataframe)
    except:  # pylint: disable=bare-except
      # need to catch and print exception since it is user visible
      _traceback.print_exc()
    return mime_bundle

  def _repr_html_(self):
    return self._dataframe._repr_html_()  # pylint: disable=protected-access

  def _repr_javascript_module_(self):
    try:
      return self._gen_js(self._preprocess_dataframe())
    except:  # pylint: disable=bare-except
      # need to catch and print exception since it is user visible
      _traceback.print_exc()

  def _gen_js(self, dataframe):
    """Returns javascript for this table."""
    columns = dataframe.columns
    data = dataframe.values

    data_formatters = {}
    header_formatters = {}
    default_formatter = _interactive_table_helper._find_formatter(  # pylint: disable=protected-access
        _DEFAULT_FORMATTERS)

    for i, _ in enumerate(columns):
      data_formatters[i] = default_formatter
      header_formatters[i] = default_formatter

    formatted_data = _interactive_table_helper._format_data(  # pylint: disable=protected-access
        data, _DEFAULT_NONUNICODE_FORMATTER, data_formatters)
    column_types = formatted_data['column_types']

    columns_and_types = []
    for i, (column_type, column) in enumerate(zip(column_types, columns)):
      columns_and_types.append((column_type, str(header_formatters[i](column))))

    column_options = []
    if self._include_index:
      # Collapse index columns to minimum necessary width. We specify 1px but
      # they will auto-expand as necessary.
      column_options = [{
          'width': '1px',
          'className': 'index_column'
      }] * self._dataframe.index.nlevels

    return """
      import "{gviz_url}";

      window.createDataTable({{
        data: {data},
        columns: {columns},
        columnOptions: {column_options},
        rowsPerPage: {num_rows_per_page},
        helpUrl: "{help_url}",
      }});
    """.format(
        gviz_url=_GVIZ_JS,
        data=formatted_data['data'],
        columns=_json.dumps(columns_and_types),
        column_options=_json.dumps(column_options),
        num_rows_per_page=self._num_rows_per_page,
        help_url=_DATA_TABLE_HELP_URL,
    )


class _JavascriptModuleFormatter(_IPython.core.formatters.BaseFormatter):
  format_type = _traitlets.Unicode(_JAVASCRIPT_MODULE_MIME_TYPE)
  print_method = _traitlets.ObjectName('_repr_javascript_module_')


def _register_jsmodule_mimetype():
  """Register _repr_javascript_module_ with the IPython display mechanism."""
  display_formatter = _IPython.get_ipython().display_formatter
  display_formatter.formatters.setdefault(
      _JAVASCRIPT_MODULE_MIME_TYPE,
      _JavascriptModuleFormatter(parent=display_formatter))


_original_formatters = {}


def enable_dataframe_formatter():
  """Enables DataTable as the default IPython formatter for Pandas DataFrames."""
  key = _JAVASCRIPT_MODULE_MIME_TYPE
  if key not in _original_formatters:
    _register_jsmodule_mimetype()
    formatters = _IPython.get_ipython().display_formatter.formatters
    _original_formatters[key] = formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', DataTable.formatter)


def disable_dataframe_formatter():
  """Restores the original IPython formatter for Pandas DataFrames."""
  key = _JAVASCRIPT_MODULE_MIME_TYPE
  if key in _original_formatters:
    formatters = _IPython.get_ipython().display_formatter.formatters
    # pop() handles the case of original_formatter = None.
    formatters[key].pop('pandas.core.frame.DataFrame')
    formatters[key].for_type_by_name('pandas.core.frame', 'DataFrame',
                                     _original_formatters.pop(key))


def load_ipython_extension(ipython):  # pylint: disable=unused-argument
  """Enable DataTable output for all Pandas dataframes."""
  enable_dataframe_formatter()


def unload_ipython_extension(ipython):  # pylint: disable=unused-argument
  """Disable DataTable output for all Pandas dataframes."""
  disable_dataframe_formatter()
