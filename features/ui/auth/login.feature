@ui
Feature: Login
  Users sign in to the shop with a username and password.

  @smoke
  Scenario: Valid login shows the products page
    Given I am on the login page
    When I log in as the "standard" user with a valid password
    Then I see the products page

  Scenario Outline: Invalid login shows an error
    Given I am on the login page
    When I log in as the "<role>" user with a <password_kind> password
    Then I see the login error "<message>"

    Examples:
      | role        | password_kind | message                                                                  |
      | locked_out  | valid         | Epic sadface: Sorry, this user has been locked out.                      |
      | standard    | invalid       | Epic sadface: Username and password do not match any user in this service |
      | no_username | valid         | Epic sadface: Username is required                                       |
