@accessibility
Feature: Login accessibility
  Key screens meet WCAG 2.x level A and AA rules.

  @smoke
  Scenario: Login page has no blocking accessibility violations
    Given I am viewing the login page
    Then the login page has no blocking accessibility violations

  Scenario: Inventory page has no blocking accessibility violations
    Given I am viewing the login page
    When I sign in as the "standard" user
    Then the inventory page has no blocking accessibility violations
