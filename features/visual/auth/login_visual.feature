@visual
Feature: Login visuals
  Key screens look the way the approved baselines say they should.

  @smoke
  Scenario: Login page matches the baseline
    Given I am viewing the login page
    Then the login page matches the baseline

  Scenario: Inventory page matches the baseline
    Given I am viewing the login page
    When I sign in as the "visual" user
    Then the inventory page matches the baseline
