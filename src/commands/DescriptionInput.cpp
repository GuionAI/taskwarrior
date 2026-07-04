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
#include <unistd.h>

#include <iostream>
#include <sstream>
#include <vector>

namespace {

////////////////////////////////////////////////////////////////////////////////
std::string readStdin() {
  std::ostringstream buffer;
  buffer << std::cin.rdbuf();
  if (std::cin.bad()) throw std::string("Failed to read description from stdin.");

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
bool isDescriptionWord(const A2& arg) {
  if (!arg.hasTag("MODIFICATION")) return false;
  if (arg._lextype != Lexer::Type::word) return false;

  std::string raw = arg.attribute("raw");
  return raw.substr(0, 7) != "before:" && raw.substr(0, 6) != "after:";
}

////////////////////////////////////////////////////////////////////////////////
bool isDescriptionPair(const A2& arg) {
  if (!arg.hasTag("MODIFICATION")) return false;
  if (arg._lextype != Lexer::Type::pair) return false;

  return arg.attribute("canonical") == "description" || arg.attribute("name") == "description";
}

////////////////////////////////////////////////////////////////////////////////
bool isModification(const A2& arg) { return arg.hasTag("MODIFICATION"); }

}  // namespace

////////////////////////////////////////////////////////////////////////////////
void applyPipedDescriptionInput() {
  auto& args = Context::getContext().cli2._args;
  if (isatty(STDIN_FILENO)) return;

  for (const auto& arg : args)
    if (isDescriptionWord(arg) || isDescriptionPair(arg)) return;

  if (Context::getContext().cli2.getCommand() == "modify")
    for (const auto& arg : args)
      if (isModification(arg)) return;

  auto description = readStdin();
  if (description == "") return;

  auto descriptionArg = descriptionModification(description);
  std::vector<A2> reconstructed;
  bool inserted = false;
  for (const auto& arg : args) {
    if (!inserted && arg.hasTag("MODIFICATION")) {
      reconstructed.push_back(descriptionArg);
      inserted = true;
    }

    reconstructed.push_back(arg);
  }

  if (!inserted) reconstructed.push_back(descriptionArg);
  args = reconstructed;
}

////////////////////////////////////////////////////////////////////////////////
