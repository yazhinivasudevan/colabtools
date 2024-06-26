# Copyright 2021 Google Inc.
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
"""Formatter used to display a data table conversion button next to dataframes."""

import uuid as _uuid
import weakref as _weakref
from google.colab import data_table as _data_table
from google.colab import output as _output
import IPython as _IPython

_ICON_SVG = """
  <svg xmlns="http://www.w3.org/2000/svg" height="24px"viewBox="0 0 24 24"
       width="24px">
    <path d="M0 0h24v24H0V0z" fill="none"/>
    <path d="M18.56 5.44l.94 2.06.94-2.06 2.06-.94-2.06-.94-.94-2.06-.94 2.06-2.06.94zm-11 1L8.5 8.5l.94-2.06 2.06-.94-2.06-.94L8.5 2.5l-.94 2.06-2.06.94zm10 10l.94 2.06.94-2.06 2.06-.94-2.06-.94-.94-2.06-.94 2.06-2.06.94z"/><path d="M17.41 7.96l-1.37-1.37c-.4-.4-.92-.59-1.43-.59-.52 0-1.04.2-1.43.59L10.3 9.45l-7.72 7.72c-.78.78-.78 2.05 0 2.83L4 21.41c.39.39.9.59 1.41.59.51 0 1.02-.2 1.41-.59l7.78-7.78 2.81-2.81c.8-.78.8-2.07 0-2.86zM5.41 20L4 18.59l7.72-7.72 1.47 1.35L5.41 20z"/>
  </svg>"""

_HINT_BUTTON_CSS = """
  <style>
    .colab-df-container {
      display:flex;
      flex-wrap:wrap;
      gap: 12px;
    }

    .colab-df-convert {
      background-color: #E8F0FE;
      border: none;
      border-radius: 50%;
      cursor: pointer;
      display: none;
      fill: #1967D2;
      height: 32px;
      padding: 0 0 0 0;
      width: 32px;
    }

    .colab-df-convert:hover {
      background-color: #E2EBFA;
      box-shadow: 0px 1px 2px rgba(60, 64, 67, 0.3), 0px 1px 3px 1px rgba(60, 64, 67, 0.15);
      fill: #174EA6;
    }

    [theme=dark] .colab-df-convert {
      background-color: #3B4455;
      fill: #D2E3FC;
    }

    [theme=dark] .colab-df-convert:hover {
      background-color: #434B5C;
      box-shadow: 0px 1px 3px 1px rgba(0, 0, 0, 0.15);
      filter: drop-shadow(0px 1px 2px rgba(0, 0, 0, 0.3));
      fill: #FFFFFF;
    }
  </style>
"""

# Cache of non-interactive dfs that still have live references and could be
# printed as interactive dfs.
_noninteractive_df_refs = _weakref.WeakValueDictionary()

# Single entry cache that stores a shallow copy of the last printed df.
_last_noninteractive_df = {}


def _convert_to_interactive(key):
  """Converts a stored df into a data table if we still hold a ref to it."""
  df = _get_dataframe(key)
  if df is not None:
    return _data_table.DataTable(df)


def _get_dataframe(key):
  if key in _last_noninteractive_df:
    return _last_noninteractive_df.pop(key)
  elif key in _noninteractive_df_refs:
    return _noninteractive_df_refs.pop(key)
  print(
      'Error: Runtime no longer has a reference to this dataframe, please'
      ' re-run this cell and try again.'
  )


def _get_last_dataframe_key():
  df_keys = list(_last_noninteractive_df.keys())
  if df_keys:
    return df_keys[0]


_output_callbacks = {}


def _df_formatter_with_interactive_hint(dataframe):
  """Alternate df formatter that includes a button to convert to interactive."""
  key = 'df-' + str(_uuid.uuid4())
  _noninteractive_df_refs[key] = dataframe

  # Ensure our last value cache only contains one item.
  _last_noninteractive_df.clear()
  _last_noninteractive_df[key] = dataframe.copy(deep=False)

  convert_func = 'convertToInteractive'
  if convert_func not in _output_callbacks:
    _output_callbacks[convert_func] = _output.register_callback(
        convert_func, _convert_to_interactive
    )
  return _get_html(dataframe, key)


def _get_html(dataframe, key):
  # pylint: disable=protected-access
  return """
  <div id="{key}">
    <div class="colab-df-container">
      {df_html}
      <button class="colab-df-convert" onclick="convertToInteractive('{key}')"
              title="Convert this dataframe to an interactive table."
              style="display:none;">
        {icon}
      </button>
      {css}
      <script>
        const buttonEl =
          document.querySelector('#{key} button.colab-df-convert');
        buttonEl.style.display =
          google.colab.kernel.accessAllowed ? 'block' : 'none';

        async function convertToInteractive(key) {{
          const element = document.querySelector('#{key}');
          const dataTable =
            await google.colab.kernel.invokeFunction('convertToInteractive',
                                                     [key], {{}});
          if (!dataTable) return;

          const docLinkHtml = 'Like what you see? Visit the ' +
            '<a target="_blank" href={data_table_url}>data table notebook</a>'
            + ' to learn more about interactive tables.';
          element.innerHTML = '';
          dataTable['output_type'] = 'display_data';
          await google.colab.output.renderOutput(dataTable, element);
          const docLink = document.createElement('div');
          docLink.innerHTML = docLinkHtml;
          element.appendChild(docLink);
        }}
      </script>
    </div>
  </div>
  """.format(
      css=_HINT_BUTTON_CSS,
      data_table_url=_data_table._DATA_TABLE_HELP_URL,
      df_html=dataframe._repr_html_(),
      icon=_ICON_SVG,
      key=key,
  )


_original_formatters = {}


def _enable_df_interactive_hint_formatter():
  """Formatter that surfaces the existence of interactive tables to user."""
  shell = _IPython.get_ipython()
  if not shell:
    return
  key = 'text/html'
  if key not in _original_formatters:
    formatters = shell.display_formatter.formatters
    _original_formatters[key] = formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', _df_formatter_with_interactive_hint
    )


def _disable_df_interactive_hint_formatter():
  """Restores the original html formatter for Pandas DataFrames."""
  shell = _IPython.get_ipython()
  if not shell:
    return
  key = 'text/html'
  if key in _original_formatters:
    formatters = shell.display_formatter.formatters
    formatters[key].pop('pandas.core.frame.DataFrame', None)
    formatters[key].for_type_by_name(
        'pandas.core.frame', 'DataFrame', _original_formatters.pop(key)
    )
