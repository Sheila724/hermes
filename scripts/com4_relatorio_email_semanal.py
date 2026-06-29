#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from com4_relatorio_email import main
sys.argv = ["com4_relatorio_email.py", "semanal"]
main()
