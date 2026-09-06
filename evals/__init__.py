"""AtBots evals: one scenario set, scored two ways.

Tier 1 drives the task loop with scripted model behaviour and gates every commit.
Tier 2 drives it with a real local model and reports rates against a baseline.
Both share the scenarios, fixtures, and evaluators in this package, which is what
makes their numbers comparable.

This package is not part of the installed wheel.
"""
