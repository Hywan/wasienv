#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import subprocess
import logging
import shutil
import stat

logger = logging.getLogger('wasienv')


class Py2CalledProcessError(subprocess.CalledProcessError):
  def __init__(self, return_code, cmd, output=None, stderr=None):
    super(Exception, self).__init__(return_code, cmd, output, stderr)
    self.return_code = return_code
    self.cmd = cmd
    self.output = output
    self.stderr = stderr


class Py2CompletedProcess:
  def __init__(self, args, return_code, stdout, stderr):
    self.args = args
    self.return_code = return_code
    self.stdout = stdout
    self.stderr = stderr

  def check(self):
    if self.return_code != 0:
      raise Py2CalledProcessError(return_code=self.return_code, cmd=self.args, output=self.stdout, stderr=self.stderr)


def check_program(cmd):
    if not os.path.exists(cmd):
        raise Exception("The program {} was not found. Is the SDK installed?\nYou can install it via: wasienv install-sdk unstable".format(os.path.basename(cmd)))


def python2_subprocess_run(cmd, check=True, input=None, *args, **kwargs):
  if input is not None:
    kwargs['stdin'] = subprocess.PIPE

  proc = subprocess.Popen(cmd, *args, **kwargs)
  stdout, stderr = proc.communicate(input)
  result = Py2CompletedProcess(cmd, proc.returncode, stdout, stderr)
  if check:
    result.check()
  return result


def run_process(cmd, check=True, input=None, *args, **kwargs):
  logger.debug("wasienv run process: {}".format(" ".join(cmd)))
  debug_text = '%sexecuted %s' % ('successfully ' if check else '', ' '.join(cmd))

  run = getattr(subprocess, "run", python2_subprocess_run)
  ret = run(cmd, check=check, input=input, *args, **kwargs)
  logger.debug(debug_text)

  return ret.return_code


def is_exe(fpath):
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

def try_to_wrap_executable(exe_name):
    target_path = os.path.join(os.getcwd(), exe_name)
    if not is_exe(target_path) or exe_name.endswith(".wasm"):
        return

    # It's a cmake file, we skip
    # CMake does some checks like the size of a struct generating
    # a file with certain contents on it and then doing a check using
    # regex. That means that we can't wrap it in a executable
    if os.path.basename(exe_name).startswith('cmTC_'):
        return

    st = os.stat(target_path)
    with open(target_path,'r') as f:
        first_bytes = f.read(4)
        # is_wasm = first_bytes == [0x00, 0x61, 0x73, 0x6d]
        is_wasm = bytearray(first_bytes) == b'\x00asm'
        f.seek(0)
        if not is_wasm:
            return

    new_target_path = "{}.wasm".format(target_path)
    shutil.copy(target_path, new_target_path)
    with open(target_path,'w') as f:
        f.write("#!/bin/bash\nwasirun {} \"$@\"\n".format(new_target_path))


    os.chmod(new_target_path, st.st_mode)

    # Copy files to the temp folder 
    # Wasm file
    temp_target_path = os.path.join('/tmp', os.path.split(new_target_path)[1])
    shutil.copy(new_target_path, temp_target_path)
    # Executable file
    temp_target_path = os.path.join('/tmp', os.path.split(target_path)[1])
    shutil.copy(target_path, temp_target_path)


def find_output_arg(args):
  """Find and remove any -o arguments.  The final one takes precedence.
  Return the final -o target along with the remaining (non-o) arguments.
  """
  outargs = []
  specified_target = None
  use_next = False
  for arg in args:
    if use_next:
      specified_target = arg
      use_next = False
      continue
    if arg == '-o':
      use_next = True
    elif arg.startswith('-o'):
      specified_target = arg[2:]
    else:
      outargs.append(arg)
  return specified_target, outargs


def set_environ():
    from constants import WASI_CC, WASI_CXX, WASI_LD, WASI_AR, WASI_RANLIB, WASI_NM

    os.environ["CC"] = WASI_CC
    os.environ["CXX"] = WASI_CXX
    os.environ["LD"] = WASI_LD
    os.environ["AR"] = WASI_AR
    os.environ["RANLIB"] = WASI_RANLIB
    os.environ["NM"] = WASI_NM

    os.environ["WASI_CC"] = WASI_CC
    os.environ["WASI_CXX"] = WASI_CXX
    os.environ["WASI_LD"] = WASI_LD
    os.environ["WASI_AR"] = WASI_AR
    os.environ["WASI_RANLIB"] = WASI_RANLIB
    os.environ["WASI_NM"] = WASI_NM


def wrap_run(f):
    def wrapped_f():
        try:
            logging.basicConfig(level=logging.INFO)
            sys.exit(f(sys.argv))
        except KeyboardInterrupt:
            logger.warning("KeyboardInterrupt")
            sys.exit(1)
    return wrapped_f
