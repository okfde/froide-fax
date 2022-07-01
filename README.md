# Froide Fax

A Django app that handles Fax sending for FragDenStaat.de.

This app works with froide and provides the following:

- a `froide_fax.fax.FaxMessageHandler` that can be configured to handle messages of type `fax`
- a model that stores a signature per user
- templates that can be included for getting a signature and sending a message as a fax.
- a `fax_tags` template tag library that provides:
  - a tag `get_signature_form` to render a form to get user's signature
  - a tag `foirequest_needs_signature` to check if an FOI request contains faxable messages and if the user should be asked to provide a signature
  - a tag `can_fax_message` that checks if a given message can be faxed
- URLs and views to:
  - store user signature
  - explicit trigger to fax a message
  - Webhook status callback of fax API provider
  - Authenticated view for PDF that should be faxed for API provider

