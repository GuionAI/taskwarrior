////////////////////////////////////////////////////////////////////////////////
//
// Copyright 2006 - 2025, Tomas Babej, Paul Beckingham, Federico Hernandez.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included
// in all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
// OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
// THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
//
// https://www.opensource.org/licenses/mit-license.php
//
////////////////////////////////////////////////////////////////////////////////

#include <cmake.h>
// cmake.h include header must come first

#include <CmdTagManage.h>
#include <Context.h>
#include <Table.h>
#include <format.h>
#include <util.h>

#include <sstream>
#include <vector>

////////////////////////////////////////////////////////////////////////////////
CmdTagManage::CmdTagManage() {
  _keyword = "tag";
  _usage = "task tag add <name> | delete <name> | list | migrate";
  _description = "Manages the registered tag list (add, delete, list, migrate)";
  _read_only = false;
  _displays_id = false;
  _uses_context = false;
  _accepts_filter = false;
  _accepts_modifications = false;
  _accepts_miscellaneous = true;
  _category = Command::Category::metadata;
}

////////////////////////////////////////////////////////////////////////////////
int CmdTagManage::execute(std::string& output) {
  std::stringstream out;
  auto words = Context::getContext().cli2.getWords();

  // Default to "list" when no subcommand given.
  std::string subcommand = words.empty() ? "list" : words[0];

  // --- tag list ---
  if (subcommand == "list") {
    auto tags = Context::getContext().tdb2.replica()->get_all_task_tags();

    if (tags.empty()) {
      Context::getContext().footnote("No tags found.");
      output = out.str();
      return 1;
    }

    Table view;
    view.width(Context::getContext().getWidth());
    view.add("Tag");
    setHeaderUnderline(view);

    for (const auto& tag : tags) {
      int row = view.addRow();
      view.set(row, 0, static_cast<std::string>(tag));
    }

    out << optionalBlankLine() << view.render() << optionalBlankLine();

    if (tags.size() == 1)
      Context::getContext().footnote("1 registered tag");
    else
      Context::getContext().footnote(format("{1} registered tags", tags.size()));

    out << '\n';

    // --- tag add <name> ---
  } else if (subcommand == "add") {
    if (words.size() < 2) {
      throw std::string("Usage: task tag add <name>");
    }

    const std::string& name = words[1];
    if (name.empty()) {
      throw std::string("Tag name must not be empty.");
    }

    Context::getContext().tdb2.replica()->register_tag(name);
    out << "Tag '" << name << "' registered.\n";

    // --- tag delete <name> ---
  } else if (subcommand == "delete") {
    if (words.size() < 2) {
      throw std::string("Usage: task tag delete <name>");
    }

    const std::string& name = words[1];
    if (name.empty()) {
      throw std::string("Tag name must not be empty.");
    }

    Context::getContext().tdb2.replica()->delete_tag(name);
    out << "Tag '" << name << "' deleted.\n";

    // --- tag migrate ---
  } else if (subcommand == "migrate") {
    // Unconditionally scan all tasks and register any tag not yet in tc_config.
    Context::getContext().tdb2.replica()->migrate_tags_from_tasks();
    auto after = Context::getContext().tdb2.replica()->get_all_task_tags();
    out << "Tag migration complete. " << after.size() << " tag(s) now registered.\n";

  } else {
    throw format("Unknown subcommand '{1}'. Usage: task tag add <name> | delete <name> | list | migrate",
                 subcommand);
  }

  output = out.str();
  return 0;
}

////////////////////////////////////////////////////////////////////////////////
