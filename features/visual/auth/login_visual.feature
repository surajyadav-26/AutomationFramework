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

  Scenario: Login page matches the baseline on a phone
    Given I am using a phone-sized screen
    And I am viewing the login page
    Then the login page matches the baseline

  Scenario: Inventory page matches the baseline on a phone
    Given I am using a phone-sized screen
    And I am viewing the login page
    When I sign in as the "visual" user
    Then the inventory page matches the baseline
