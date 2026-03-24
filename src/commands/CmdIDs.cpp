////////////////////////////////////////////////////////////////////////////////
//
// Copyright 2006 - 2021, Tomas Babej, Paul Beckingham, Federico Hernandez.
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

#include <CmdIDs.h>
#include <Context.h>
#include <Filter.h>
#include <shared.h>

#include <algorithm>
#include <sstream>

std::string zshColonReplacement = ",";

////////////////////////////////////////////////////////////////////////////////
CmdIDs::CmdIDs() {
  _keyword = "ids";
  _usage = "task <filter> ids";
  _description = "Shows the IDs of matching tasks, as a range";
  _read_only = true;
  _displays_id = true;
  _uses_context = false;
  _accepts_filter = true;
  _accepts_modifications = false;
  _accepts_miscellaneous = false;
  _category = Command::Category::metadata;
}

////////////////////////////////////////////////////////////////////////////////
int CmdIDs::execute(std::string& output) {
  // Apply filter.
  Filter filter;
  std::vector<Task> filtered;
  filter.subset(filtered);

  // Collect 8-char hex UUID prefixes for matching tasks.
  std::vector<std::string> ids;
  for (auto& task : filtered)
    if (!task.id.empty()) ids.push_back(task.id);

  std::sort(ids.begin(), ids.end());
  output = join(" ", ids) + '\n';

  Context::getContext().headers.clear();
  return 0;
}

////////////////////////////////////////////////////////////////////////////////
CmdCompletionIds::CmdCompletionIds() {
  _keyword = "_ids";
  _usage = "task <filter> _ids";
  _description = "Shows the IDs of matching tasks, in the form of a list";
  _read_only = true;
  _displays_id = true;
  _uses_context = false;
  _accepts_filter = true;
  _accepts_modifications = false;
  _accepts_miscellaneous = false;
  _category = Command::Category::internal;
}

////////////////////////////////////////////////////////////////////////////////
int CmdCompletionIds::execute(std::string& output) {
  // Apply filter.
  Filter filter;
  std::vector<Task> filtered;
  filter.subset(filtered);

  std::vector<std::string> ids;
  for (auto& task : filtered)
    if (task.getStatus() != Task::deleted && task.getStatus() != Task::completed)
      ids.push_back(task.id);

  std::sort(ids.begin(), ids.end());
  output = join("\n", ids) + '\n';

  Context::getContext().headers.clear();
  return 0;
}

////////////////////////////////////////////////////////////////////////////////
CmdZshCompletionIds::CmdZshCompletionIds() {
  _keyword = "_zshids";
  _usage = "task <filter> _zshids";
  _description = "Shows the IDs and descriptions of matching tasks";
  _read_only = true;
  _displays_id = true;
  _uses_context = false;
  _accepts_filter = true;
  _accepts_modifications = false;
  _accepts_miscellaneous = false;
  _category = Command::Category::internal;
}

////////////////////////////////////////////////////////////////////////////////
int CmdZshCompletionIds::execute(std::string& output) {
  // Apply filter.
  Filter filter;
  std::vector<Task> filtered;
  filter.subset(filtered);

  std::stringstream out;
  for (auto& task : filtered)
    if (task.getStatus() != Task::deleted && task.getStatus() != Task::completed)
      out << task.id << ':' << str_replace(task.get("description"), ":", zshColonReplacement)
          << '\n';

  output = out.str();

  Context::getContext().headers.clear();
  return 0;
}

////////////////////////////////////////////////////////////////////////////////
CmdUUIDs::CmdUUIDs() {
  _keyword = "uuids";
  _usage = "task <filter> uuids";
  _description = "Shows the UUIDs of matching tasks, as a space-separated list";
  _read_only = true;
  _displays_id = false;
  _uses_context = false;
  _accepts_filter = true;
  _accepts_modifications = false;
  _accepts_miscellaneous = false;
  _category = Command::Category::metadata;
}

////////////////////////////////////////////////////////////////////////////////
int CmdUUIDs::execute(std::string& output) {
  // Apply filter.
  Filter filter;
  std::vector<Task> filtered;
  filter.subset(filtered);

  std::vector<std::string> uuids;
  uuids.reserve(filtered.size());
  for (auto& task : filtered) uuids.push_back(task.get("uuid"));

  std::sort(uuids.begin(), uuids.end());
  output = join(" ", uuids) + '\n';

  Context::getContext().headers.clear();
  return 0;
}

////////////////////////////////////////////////////////////////////////////////
CmdCompletionUuids::CmdCompletionUuids() {
  _keyword = "_uuids";
  _usage = "task <filter> _uuids";
  _description = "Shows the UUIDs of matching tasks, as a list";
  _read_only = true;
  _displays_id = false;
  _uses_context = false;
  _accepts_filter = true;
  _accepts_modifications = false;
  _accepts_miscellaneous = false;
  _category = Command::Category::internal;
}

////////////////////////////////////////////////////////////////////////////////
int CmdCompletionUuids::execute(std::string& output) {
  // Apply filter.
  Filter filter;
  std::vector<Task> filtered;
  filter.subset(filtered);

  std::vector<std::string> uuids;
  uuids.reserve(filtered.size());
  for (auto& task : filtered) uuids.push_back(task.get("uuid"));

  std::sort(uuids.begin(), uuids.end());
  output = join("\n", uuids) + '\n';

  Context::getContext().headers.clear();
  return 0;
}

////////////////////////////////////////////////////////////////////////////////
CmdZshCompletionUuids::CmdZshCompletionUuids() {
  _keyword = "_zshuuids";
  _usage = "task <filter> _zshuuids";
  _description = "Shows the UUIDs and descriptions of matching tasks";
  _read_only = true;
  _displays_id = false;
  _uses_context = false;
  _accepts_filter = true;
  _accepts_modifications = false;
  _accepts_miscellaneous = false;
  _category = Command::Category::internal;
}

////////////////////////////////////////////////////////////////////////////////
int CmdZshCompletionUuids::execute(std::string& output) {
  // Apply filter.
  Filter filter;
  std::vector<Task> filtered;
  filter.subset(filtered);

  std::stringstream out;
  for (auto& task : filtered)
    out << task.get("uuid") << ':' << str_replace(task.get("description"), ":", zshColonReplacement)
        << '\n';

  output = out.str();

  Context::getContext().headers.clear();
  return 0;
}

///////////////////////////////////////////////////////////////////////////////
