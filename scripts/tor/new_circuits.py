#!/usr/bin/env python3
import functools

from stem import Signal
from stem.control import Controller

def main():
  with Controller.from_socket_file() as controller:
    controller.authenticate()
    controller.signal(Signal.NEWNYM)


if __name__ == '__main__':
  main()
