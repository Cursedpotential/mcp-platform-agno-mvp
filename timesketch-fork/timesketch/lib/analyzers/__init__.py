# Copyright 2018 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Analyzer module.

ADR-0060 / WP-E01 disable-not-delete seam: upstream `google/timesketch` ships its
analyzer set registered as an import-time side effect (each module below calls
``manager.AnalysisManager.register_analyzer`` when imported). All of that upstream
DFIR/security analyzer set is neutralized by default for the personal-case fork --
none of the files are removed, renamed, or edited; this is the single control point
that decides whether their registration import runs. Flip
``TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS=1`` to restore the full upstream set
unchanged (e.g. to diff behavior against stock Timesketch, or because a later
packet decides a specific analyzer -- e.g. ``tagger`` or ``llm_log_analyzer`` -- is
worth keeping live). See ``timesketch-fork/UPSTREAM.md`` for the full inventory and
rationale. Personal-case relationship/life-event analyzers are a later packet
(WP-E02+); when added they belong in their own isolated module imported
unconditionally below, independent of this flag.
"""

import os

_ENABLE_UPSTREAM_ANALYZERS = os.environ.get(
    "TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS", ""
).strip().lower() in ("1", "true", "yes", "on")

if _ENABLE_UPSTREAM_ANALYZERS:
    # Register all upstream analyzers here by importing them.
    from timesketch.lib.analyzers import account_finder
    from timesketch.lib.analyzers import browser_search
    from timesketch.lib.analyzers import browser_timeframe
    from timesketch.lib.analyzers import chain
    from timesketch.lib.analyzers import domain
    from timesketch.lib.analyzers import expert_sessionizers
    from timesketch.lib.analyzers import feature_extraction
    from timesketch.lib.analyzers import gcp_logging
    from timesketch.lib.analyzers import geoip
    from timesketch.lib.analyzers import hashr_lookup
    from timesketch.lib.analyzers import login
    from timesketch.lib.analyzers import phishy_domains
    from timesketch.lib.analyzers import safebrowsing
    from timesketch.lib.analyzers import sessionizer
    from timesketch.lib.analyzers import sigma_tagger
    from timesketch.lib.analyzers import similarity_scorer
    from timesketch.lib.analyzers import ssh_sessionizer
    from timesketch.lib.analyzers import gcp_servicekey
    from timesketch.lib.analyzers import ntfs_timestomp
    from timesketch.lib.analyzers import yetiindicators
    from timesketch.lib.analyzers import win_crash
    from timesketch.lib.analyzers import win_evtxgap
    from timesketch.lib.analyzers import tagger
    from timesketch.lib.analyzers import llm_log_analyzer

    import timesketch.lib.analyzers.authentication
    import timesketch.lib.analyzers.contrib
    import timesketch.lib.analyzers.dfiq_plugins
