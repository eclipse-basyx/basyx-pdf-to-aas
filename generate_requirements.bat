pip-compile %* -o requirements.txt --strip-extras
pip-compile %* --extra=demo -o demo-requirements.txt --strip-extras
pip-compile %* --extra=dev -o dev-requirements.txt -c demo-requirements.txt --strip-extras