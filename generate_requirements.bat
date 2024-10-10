pip-compile -q -o requirements.txt --strip-extras
pip-compile -q --extra=demo -o demo-requirements.txt --strip-extras
pip-compile -q --extra=dev -o dev-requirements.txt -c demo-requirements.txt --strip-extras