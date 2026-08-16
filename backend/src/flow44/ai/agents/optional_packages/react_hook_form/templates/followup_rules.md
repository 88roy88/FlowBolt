### react-hook-form — forms
- react-hook-form is already installed — extend an existing form through its current useForm instance rather than adding a parallel useState.
- Add any new field to the FormValues type and register it with the same validation-rule style the form already uses.
- Read new errors as errors.field?.message, matching how existing fields display theirs.
