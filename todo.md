# TODO

This application is a simple single user TODO list.

## Conventions

- This app serves plain, dense HTML. No JavaScript framework. No CSS frameworks.
  A little inline CSS in the `<head>` is fine and encouraged: serif body
  text, generous margins, hairline rules between sections. JavaScript
  for functionality can be inline or in a single `<script>` block in
  the header.

## Paths

- `/` - the index page. Lists any TODO items that have been added. At
  the bottom is a form to add a new TODO, it should just be a single
  text field and an "Add" button. It POSTs to `/add`. Each item in the
  list has a checkbox. Clicking the checkbox for at item makes a
  `DELETE` request to `/item/:id` and reloads the index page.
- `/add` - accepts a POST request with a TODO item to add. The item
  should be added to the list in memory (along with an auto generated
  unique id), then the view should reply with a 302 redirect back to `/`
- `/item/:id` - a `GET` request should show the TODO item with that id
  (or a 404 if none match) along with a button to delete it, and a
  hypertext link back to `/`. A `DELETE` request to this endpoint
  should remove the item with that id from memory (or 404 if none
  match) and then respond with a 302 redirect back to the index.
