# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changes

- keep the consent page responsive while the reference lists load, instead of blocking
  every other interaction until the last preview has resolved
- avoid loading each reference list twice per visit
- pulse the loading bar until the first list reports, instead of filling it to 90% and
  dropping back to the real count

### Deprecated

### Removed

### Fixed

- show the referenced items in the reference list previews again, which stayed blank

### Security

## [1.2.0] - 2026-09-15

### Added

- show a single progress bar while the consent page loads its reference lists, which
  advances one step per list and replaces the per-list spinners

### Changes

- hold the reference lists back until all of them have loaded, so they appear together
  instead of popping in one after the other
- render the page shell right away instead of hiding it behind a page-level spinner,
  so the progress bar is on screen from the first paint
- link the logged-in person's email via `mailto:` and their orcid id to orcid.org,
  which opens in a new tab
- assign a `library` icon to the `ResourceSeries` entity type, which fell back to the
  generic unknown-type icon
- show `start` in the `ResourceSeries` preview, matching the display config in mex-admin

### Removed

- drop the stop-gap `ResourceSeries` translations from the consent catalog, now that
  mex-model ships them and its entries win the catalog merge anyway

### Fixed

- fix the loading bar and user data placeholder flashing on logout: logging out now
  redirects straight to `/login` instead of bouncing through the consent page, and the
  placeholder is gated like the bar
- fix the previous session's results flashing when logging back in: the lists now also
  wait for the frontend to finish hydrating and for a user to be present
- fix reference identifiers in the previews never resolving, leaving the values as
  skeletons: resolution now runs off the fetch that produced the items, instead of a
  concurrent event that looped over an empty list
- fix the logout button doing nothing while the reference lists were still loading:
  the lists now fetch in background events off the event loop, instead of holding the
  session's exclusive event lock across ten blocking backend calls

## [1.1.1] - 2026-09-14

### Changes

- inline the MEx wordmark as an svg component, so it no longer depends on the assets path

## [1.1.0] - 2026-09-14

### Added

- `MEX_CONSENT_CATALOG_URL` to configure the catalog that items link out to

### Changes

- flatten the user menu dropdown into an inline user name and logout button
- render the nav bar as a solid accent surface with the MEx wordmark logo
- show one paginated list per entity type and reference field, derived from the model,
  instead of three lists that merged several fields each

### Fixed

- consent page no longer downloads every referencing item to render one page of five

## [1.0.1] - 2026-09-09

### Changes

- new template https://github.com/robert-koch-institut/mex-template/releases/tag/2.0.1
- pin light theme in alignment with mex-admin and mex-drop

## [1.0.0] - 2026-09-09

### Added

- add `ConsentSettings.consent_text_de` and `ConsentSettings.consent_text_en`, holding
  the consent markdown directly, configurable via `MEX_CONSENT_TEXT_DE` and
  `MEX_CONSENT_TEXT_EN`
- add `scripts/seed_test_users.py` to ingest artificial items into the backend and
  render the first three artificial persons into the LDAP mock template

### Changes

- new template https://github.com/robert-koch-institut/mex-template/releases/tag/2.0.0
- upgrade mex-backend to 4.4 and mex-common to 3.4
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
