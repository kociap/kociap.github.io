import sys
import os
import re
from dataclasses import dataclass
from dateutil import parser as dateparser
import datetime

TEMPLATE_EXTENSION = "tp"
CONTENT_EXTENSION = "ct"

# TODO: Write a tokeniser to properly split text into tokens instead of relying
#       on regexes.

def read_file(path):
  with open(path, "r") as file:
    return file.read()

def make_absolute_link(path):
  # Remove the extension.
  link = os.path.splitext(path)[0]
  # Prepend slash or remove the leading period.
  if link.startswith("."):
    link = link[1:]

  if not link.startswith("/"):
    link = "/" + link

  # We turn the index page into an slash since it's the root.
  if link == "/index":
    link = "/"

  return link

def make_unix_link(path):
  link = make_absolute_link(path)
  if link == "/":
    link = "~"
  else:
    link = "~" + link
  return link

@dataclass
class Metadata:
  title: str
  date: datetime

def read_metadata(content):
  date = None
  title = None

  for line in content.splitlines():
    if not line.startswith("--"):
      break

    line = line[2:].strip()
    if re.match(r'date\W*:', line):
      date = line.split(":")[1].strip()
      date = dateparser.parse(date)
    elif re.match(r'title\W*:', line):
      title = line.split(":")[1].strip()

  return Metadata(title, date)

def remove_metadata(content):
  def emit_lines(content):
    metadata_ended = False
    for line in content.splitlines(keepends = True):
      if metadata_ended:
        yield line
      elif not line.startswith("--"):
        metadata_ended = True
        yield line

  return "".join(emit_lines(content))

@dataclass
class Field_Context:
  path: str
  link: str
  unix_link: str
  title: str
  date: datetime
  content: str

def replace_field(field, ctx):
  if not field.startswith("#!"):
    return field

  program = field[3:-1].strip()
  tokens = list(filter(len, program.split(" ")))
  command = tokens[0]
  if command == "content":
    return ctx.content
  elif command == "link":
    return ctx.link
  elif command == "unix-link":
    return ctx.unix_link
  elif command == "title":
    if not ctx.title:
      raise RuntimeError(f"requested title, but no title provided in {ctx.path}")
    return ctx.title
  elif command == "date":
    if not ctx.date:
      raise RuntimeError(f"requested date, but no date provided in {ctx.path}")
    # Reformat the date to a standard format
    return ctx.date.strftime("%Y-%m-%d")
  elif command == "list-of":
    list_name = tokens[1]
    template_path = f"list-{list_name}.{TEMPLATE_EXTENSION}"
    if not os.path.exists(template_path):
      raise RuntimeError(
          f"list file for '{list_name}' is missing. create 'list-{list_name}.{TEMPLATE_EXTENSION}")

    template_content = read_file(template_path)
    # Get all files in the list directory.
    files = [os.path.join(list_name, f) for f in os.listdir(list_name)
              if os.path.isfile(os.path.join(list_name, f))
                and os.path.splitext(f)[1] == f".{CONTENT_EXTENSION}"]
    entries = []
    dates = []
    for entry in files:
      entry_link = make_absolute_link(entry)
      entry_unix_link = make_unix_link(entry)
      entry_content = read_file(entry).strip()
      metadata = read_metadata(entry_content)
      entry_content = remove_metadata(entry_content)
      ctx = Field_Context(entry, entry_link, entry_unix_link, metadata.title,
                          metadata.date, entry_content)
      entries.append(replace_fields(template_content, ctx))
      dates.append(metadata.date.timestamp())
    # Order descending by age. Compare only timestamps.
    dates, entries = zip(*sorted(zip(dates, entries), key = lambda e: e[0],
                                 reverse = True))
    return "\n".join(entries)
  else:
    raise RuntimeError(f"invalid command '{command}'")

# replace_fields
#
# Recursively replace fields with their corresponding content using the current
# context.
#
def replace_fields(content, ctx):
  while True:
    splits = re.split(r'(#!{.*?})', content)
    if len(splits) == 1:
      break

    parts = [replace_field(field, ctx) for field in splits]
    content = "".join(parts)
  return content

def build_page(template, page):
  page_link = make_absolute_link(page)
  page_unix_link = make_unix_link(page)
  page_content = read_file(page).strip()
  metadata = read_metadata(page_content)
  page_content = remove_metadata(page_content)
  ctx = Field_Context(page, page_link, page_unix_link, metadata.title,
                      metadata.date, page_content)
  return replace_fields(template, ctx)

def main():
  if len(sys.argv) < 2:
    return -1

  template = sys.argv[1]
  pages = sys.argv[2:]
  template_source = read_file(template)
  for page in pages:
    built_page_source = build_page(template_source, page)
    output_directory = f"build/{os.path.splitext(page)[0] + '.html'}"
    os.makedirs(os.path.dirname(output_directory), exist_ok = True)
    with open(output_directory, "w") as file:
      file.write(built_page_source)

sys.exit(main())
