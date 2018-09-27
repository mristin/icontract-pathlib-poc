icontract-pathlib-poc
=====================

icontract-pathlib-poc is a proof-of-concept annotation with contracts of the standard library ``pathlib``.

To build the documentation (on Linux):

.. code-block:: bash

    git clone https://github.com/mristin/icontract-pathlib-poc.git
    cd icontract-pathlib-poc
    python3 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt
    cd docs
    make html

    # Show the documentation
    firefox build/html/index.html
