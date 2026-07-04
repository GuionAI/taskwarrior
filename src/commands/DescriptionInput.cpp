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

#include <DescriptionInput.h>
#include <Context.h>
#include <format.h>

#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>

namespace {

////////////////////////////////////////////////////////////////////////////////
bool splitInlineOption(const std::string& raw, const std::string& option, std::string& value) {
  if (raw.size() <= option.size()) return false;
  if (raw.compare(0, option.size(), option) != 0) return false;
  if (raw[option.size()] != ':' && raw[option.size()] != '=') return false;

  value = raw.substr(option.size() + 1);
  return true;
}

////////////////////////////////////////////////////////////////////////////////
std::string readStdin() {
  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  if (std::cin.bad() || buffer.fail()) throw std::string("Failed to read description from stdin.");

  return buffer.str();
}

////////////////////////////////////////////////////////////////////////////////
std::string readFile(const std::string& path) {
  std::ifstream in(path.c_str(), std::ios::in | std::ios::binary);
  if (!in) throw format("Failed to read description from file '{1}'.", path);

  std::ostringstream buffer;
  buffer << in.rdbuf();
  if (in.bad() || buffer.fail()) throw format("Failed to read description from file '{1}'.", path);

  return buffer.str();
}

////////////////////////////////////////////////////////////////////////////////
A2 descriptionModification(const std::string& description) {
  A2 arg("description:", Lexer::Type::pair);
  arg.attribute("name", "description");
  arg.attribute("separator", ":");
  arg.attribute("canonical", "description");
  arg.attribute("value", description);
  arg.tag("MODIFICATION");
  arg.tag("DESCRIPTION_INPUT");
  return arg;
}

////////////////////////////////////////////////////////////////////////////////
bool isDescriptionInputOption(const std::string& raw) {
  std::string unused;
  return raw == "--stdin" || raw == "--file" || raw == "--description" ||
         splitInlineOption(raw, "--file", unused) || splitInlineOption(raw, "--description", unused);
}

////////////////////////////////////////////////////////////////////////////////
bool isPositionalDescriptionWord(const A2& arg) {
  if (!arg.hasTag("MODIFICATION")) return false;
  if (arg._lextype != Lexer::Type::word) return false;

  std::string raw = arg.attribute("raw");
  return raw.substr(0, 7) != "before:" && raw.substr(0, 6) != "after:";
}

}  // namespace

////////////////////////////////////////////////////////////////////////////////
void applyDescriptionInputOptions() {
  auto& args = Context::getContext().cli2._args;
  std::vector<A2> reconstructed;
  bool found = false;
  std::string description;

  for (size_t i = 0; i < args.size(); ++i) {
    const auto& arg = args[i];
    const auto raw = arg.attribute("raw");
    std::string value;

    if (raw == "--stdin") {
      if (found) throw std::string("Specify only one of --stdin, --file, or --description.");
      description = readStdin();
      found = true;
      continue;
    }

    if (raw == "--file") {
      if (found) throw std::string("Specify only one of --stdin, --file, or --description.");
      if (i + 1 == args.size()) throw std::string("The --file option requires a path.");
      description = readFile(args[++i].attribute("raw"));
      found = true;
      continue;
    }

    if (splitInlineOption(raw, "--file", value)) {
      if (found) throw std::string("Specify only one of --stdin, --file, or --description.");
      description = readFile(value);
      found = true;
      continue;
    }

    if (raw == "--description") {
      if (found) throw std::string("Specify only one of --stdin, --file, or --description.");
      if (i + 1 == args.size()) throw std::string("The --description option requires text.");
      description = args[++i].attribute("raw");
      found = true;
      continue;
    }

    if (splitInlineOption(raw, "--description", value)) {
      if (found) throw std::string("Specify only one of --stdin, --file, or --description.");
      description = value;
      found = true;
      continue;
    }

    reconstructed.push_back(arg);
  }

  if (!found) return;

  for (const auto& arg : reconstructed)
    if (isDescriptionInputOption(arg.attribute("raw")) || isPositionalDescriptionWord(arg))
      throw std::string(
          "Description input options cannot be combined with positional description text.");

  reconstructed.push_back(descriptionModification(description));
  args = reconstructed;
}

////////////////////////////////////////////////////////////////////////////////
