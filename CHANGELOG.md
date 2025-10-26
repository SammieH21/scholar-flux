# Changelog

All notable changes to scholar-flux will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.1.0] - 10/26/2025
### Added
- Github Workflows now support uploads to pypi
- In future patches, We'll aim to document and continue working toward backward compatibility in future releases to minimize breaking changes on updates

### Security
- The pre-initialized scholar_flux.masker now uses a `FuzzyKeyMaskingPattern` to mask email strings in parameter
  dictionaries. This pattern will mask email fields that are named some after variation of the word, `mail`, during
  request retrieval.
