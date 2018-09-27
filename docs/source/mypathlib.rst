mypathlib
=========

icontract does not prevent endless loops at the moment. This is a missing feature in icontract, and needs yet
to be discussed, designed and implemented. This is not a blocker, we just haven't implemented it yet.

sphinx-icontract only recognizes an implication if ``not A or B``. Hence, I always put a "not" even though it might be
unnecessary (``not (not A) or B`` will render to ``not A => B``). This is a limitation of sphinx-icontract and can
be fixed.

I noted with ``???`` whenever I was not sure about something.

These contracts are neither complete nor did I spend much time thinking whether they can be made more beautiful.
Hence, they are only an illustration how the contracts might look like -- the implementer or somebody more familiar
with the module would have done a much better job.

It took me about 3 hours and 15 minutes to annotate the code with contracts.


.. autoclass:: mypathlib.PurePath
    :members:
    :special-members:

.. autoclass:: mypathlib.Path
    :members:
    :special-members:
