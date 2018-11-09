#!/usr/bin/python
# Compresses the files for one game into a single JavaScript file.
#
# Copyright 2013 Google Inc.
# https://github.com/google/blockly-games
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# This script generates two files:
#   compressed.js
#   uncompressed.js
# The compressed file is a concatenation of all the relevant JavaScript which
# has been run through Google's Closure Compiler.
# The uncompressed file is a script that loads in each JavaScript file
# one by one.  This takes much longer for a browser to load, but is useful
# when debugging code since line numbers are meaningful and variables haven't
# been renamed.  The uncompressed file also allows for a faster development
# cycle since there is no need to rebuild or recompile, just reload.

import json
import os.path
import re
import subprocess
import sys

# Define a warning message for all the generated files.
WARNING = '// Automatically generated file.  Do not edit!\n'


def main(name, lang):
  if lang != None:
    language(name, lang)
  else:
    # Extract the list of supported languages from boot.js.
    # This is a bit fragile.
    boot = open('appengine/common/boot.js', 'r')
    js = ' '.join(boot.readlines())
    boot.close()
    m = re.search('\[\'BlocklyGamesLanguages\'\] = (\[[-,\'\\s\\w]+\])', js)
    if not m:
      print("Can't find BlocklyGamesLanguages in boot.js")
      raise
    langs = m.group(1)
    langs = langs.replace("'", '"')
    langs = json.loads(langs)
    for lang in langs:
      language(name, lang)


def language(name, lang):
  if os.path.exists('appengine/third-party/blockly/msg/js/%s.js' % lang):
    # Convert 'pt-br' to 'pt.br'.
    core_language = 'Blockly.Msg.' + lang.replace('-', '.')
  else:
    core_language = 'Blockly.Msg.en'
  f = open('appengine/%s/generated/%s/msg.js' % (name, lang), 'w')
  f.write(WARNING)
  f.write("goog.provide('BlocklyGames.Msg');\n")
  f.write("goog.require('%s');\n" % core_language)
  f.close()
  write_uncompressed(name, lang)
  write_compressed(name, lang)


def write_uncompressed(name, lang):
  print('\n%s - %s - uncompressed:' % (name.title(), lang))
  cmd = ['third-party/build/closurebuilder.py',
      '--root=appengine/third-party/',
      '--root=appengine/generated/%s/' % lang,
      '--root=appengine/js/',
      '--namespace=%s' % name.replace('/', '.').title(),
      '--output_mode=list']
  directory = name
  while directory:
    cmd.append('--root=appengine/%s/generated/%s/' % (directory, lang))
    cmd.append('--root=appengine/%s/js/' % directory)
    (directory, sep, fragment) = directory.rpartition(os.path.sep)
  try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
  except:
    print("Failed to Popen: %s" & cmd)
    raise
  files = readStdout(proc)

  if name == 'pond/docs':
    path = '../'
  else:
    path = ''
  prefix = 'appengine/'
  srcs = []
  for file in files:
    file = file.strip()
    if file[:len(prefix)] == prefix:
      file = file[len(prefix):]
    else:
      raise(Exception('"%s" is not in "%s".' % (file, prefix)))
    srcs.append('"%s%s"' % (path, file))
  f = open('appengine/%s/generated/%s/uncompressed.js' % (name, lang), 'w')
  f.write("""%s
(function() {
  var srcs = [
      %s
  ];
  function loadScript() {
    var src = srcs.shift();
    if (src) {
      var script = document.createElement('script');
      script.src = src;
      script.type = 'text/javascript';
      script.onload = loadScript;
      document.head.appendChild(script);
    }
  }
  loadScript();
})();
""" % (WARNING, ',\n      '.join(srcs)))
  f.close()


def trim_licence(code):
  """Trim down Google's Apache licences.

  JS Compiler preserves dozens of Apache licences in the Blockly code.  Trim
  these down to one-liners if they belong to Google.

  Args:
    code: Large blob of compiled source code.

  Returns:
    Code with Google's Apache licences trimmed down.
  """
  apache2 = re.compile("""/\\*

 [\\w ]+

 (Copyright \\d+ Google Inc.)
 https://developers.google.com/blockly/

 Licensed under the Apache License, Version 2.0 \\(the "License"\\);
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
\\*/""")
  return re.sub(apache2, r"\n// \1  Apache License 2.0", code)


def write_compressed(name, lang):
  print('\n%s - %s - compressed:' % (name.title(), lang))

  cmd = [
    'java',
    '-jar', 'third-party/closure-compiler.jar',
    '--generate_exports',
    '--compilation_level', 'ADVANCED_OPTIMIZATIONS',
    '--dependency_mode=STRICT',
    '--externs', 'externs/gviz-externs.js',
    '--externs', 'externs/interpreter-externs.js',
    '--externs', 'externs/prettify-externs.js',
    '--externs', 'externs/soundJS-externs.js',
    '--externs', 'externs/storage-externs.js',
    '--externs', 'appengine/third-party/blockly/externs/svg-externs.js',
    '--language_out', 'ECMASCRIPT5_STRICT',
    '--entry_point=%s' % name.replace('/', '.').title(),
    "--js='appengine/third-party/**.js'",
    "--js='!appengine/third-party/blockly/*.js'",
    "--js='!appengine/third-party/blockly/tests/**.js'",
    "--js='!appengine/third-party/blockly/externs/**.js'",
    "--js='!appengine/third-party/blockly/demos/**.js'",
    "--js='appengine/generated/%s/*.js'" % lang,
    "--js='appengine/js/*.js'",
    '--warning_level', 'QUIET',
  ]
  directory = name
  while directory:
    cmd.append("--js='appengine/%s/generated/%s/*.js'" % (directory, lang))
    cmd.append("--js='appengine/%s/js/*.js'" % directory)
    (directory, sep, fragment) = directory.rpartition(os.path.sep)
  try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
  except:
    print("Failed to Popen: %s" % cmd)
    raise
  script = readStdout(proc)
  script = ''.join(script)
  script = trim_licence(script)

  f = open('appengine/%s/generated/%s/compressed.js' % (name, lang), 'w')
  f.write(WARNING)
  f.write(script)
  f.close()


def readStdout(proc):
  data = proc.stdout.readlines()
  # Python 2 reads stdout as text.
  # Python 3 reads stdout as bytes.
  return list(map(lambda line:
      type(line) == str and line or str(line, 'utf-8'), data))


if __name__ == '__main__':
  if len(sys.argv) == 2:
    main(sys.argv[1], None)
  elif len(sys.argv) == 3:
    main(sys.argv[1], sys.argv[2])
  else:
    print('Format: %s <appname> [<language>]' % sys.argv[0])
    sys.exit(2)
