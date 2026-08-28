# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- add `ConsentSettings.consent_text_de` and `ConsentSettings.consent_text_en`, holding
  the consent markdown directly, configurable via `MEX_CONSENT_TEXT_DE` and
  `MEX_CONSENT_TEXT_EN`
- add `scripts/seed_test_users.py` to ingest artificial items into the backend and
  render the first three artificial persons into the LDAP mock template

### Changes

- split `mex-consent` out of `mex-admin` as a standalone repository: this project now
  contains only the GDPR consent micro-page and the LDAP login that guards it
- rename the package `mex.admin` to `mex.consent` and flatten the former
  `mex.admin.consent` sub-package into it
- rename the console scripts `admin`, `admin-api` and `admin-frontend` to `consent`,
  `consent-api` and `consent-frontend`
- rename the settings class `AdminSettings` to `ConsentSettings` and the environment
  variable prefix from `MEX_ADMIN_` to `MEX_CONSENT_`
- serve the consent page at `/` and the LDAP login at `/login` (were `/consent` and
  `/login-ldap`)
- reset the version to 0.1.0 and truncate the changelog inherited from `mex-admin`
- rename `State.user_ldap` to `State.user`, now that it is the only user
- rename the login page component `ldap_login` to `index` and inline the
  single-caller `login_form` helper into it

### Deprecated

### Removed

- remove the `MEX_CONSENT_ASSETS_DIR` setting and the `assets/consent_de.md` and
  `assets/consent_en.md` files, the consent text is a setting now and no longer needs
  an assets directory to resolve against
- drop the contact point accounts and the `Funktion` organizational unit from
  `assets/raw-data/ldap/data.ldif.TEMPLATE`
- remove the metadata admin editor: the `home`, `search`, `advanced-search`, `create`,
  `edit`, `merge`, `ingest` and `rules` modules and their tests
- remove the MEx username/password login, `mex.consent.security` and the
  `MEX_ADMIN_USER_DATABASE` setting; the consent page authenticates via LDAP only
- remove editor-only shared modules `logo`, `style_helper`, `search_reference_dialog`,
  `value_label_select` and `types`, and prune the admin-editor entries from the
  translation catalogs

### Fixed

- fix the pagination of the consent category lists: `skip` was applied to each
  reference field separately and the per-field totals were summed, so the first page
  showed up to `limit` items per reference field (with duplicates) and the trailing
  pages were empty; the reference fields are now unioned and deduplicated before
  paginating, because the backend combines multiple reference filters with AND

- drop an assignment to an undeclared `is_loading` attribute in the error branch of
  `ConsentState.get_consent`

### Security
