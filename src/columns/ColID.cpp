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

#include <ColID.h>

////////////////////////////////////////////////////////////////////////////////
ColumnID::ColumnID() {
  _name = "id";
  _style = "short";
  _label = "ID";
  _modifiable = false;
  _styles = {"short"};
  _examples = {"42"};
}

////////////////////////////////////////////////////////////////////////////////
// Set the minimum and maximum widths for the value.
void ColumnID::measure(Task& task, unsigned int& minimum, unsigned int& maximum) {
  minimum = maximum = (unsigned int)task.id.length();
}

////////////////////////////////////////////////////////////////////////////////
void ColumnID::render(std::vector<std::string>& lines, Task& task, int width, Color& color) {
  // Completed and deleted tasks have no ID.
  if (!task.id.empty())
    renderStringRight(lines, width, color, task.id);
  else
    renderStringRight(lines, width, color, "-");
}

////////////////////////////////////////////////////////////////////////////////
