pip-compile %* -o requirements.txt --strip-extras
pip-compile %* --extra=demo -o demo-requirements.txt --strip-extras
pip-compile %* --extra=eval -o eval-requirements.txt -c demo-requirements.txt --strip-extras
pip-compile %* --extra=dev -o dev-requirements.txt -c eval-requirements.txt --strip-extras