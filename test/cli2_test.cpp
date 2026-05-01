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

#include <CLI2.h>
#include <Context.h>
#include <Lexer.h>
#include <test.h>

namespace {

// Build a FILTER-tagged A2 with the given raw text and lex type.
A2 makeFilterArg(const std::string& raw, Lexer::Type lextype) {
  A2 a(raw, lextype);
  a.tag("FILTER");
  return a;
}

// Reset and seed CLI2 state for one predicate test.
void seed(CLI2& cli2,
          const std::vector<std::string>& uuid_list,
          const std::vector<A2>& args) {
  cli2._uuid_list = uuid_list;
  cli2._args = args;
  cli2._pure_uuid_filter = false;
}

}  // namespace

////////////////////////////////////////////////////////////////////////////////
int TEST_NAME(int, char**) {
  UnitTest t(15);
  Context context;
  Context::setContext(&context);
  CLI2& cli2 = context.cli2;

  // Empty _uuid_list → false.
  seed(cli2, {}, {makeFilterArg("status:pending", Lexer::Type::pair)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, false,
       "detectPureUuidFilter: empty uuid_list stays false");

  // Single 8-char prefix arg, FILTER-tagged, raw matches uuid_list[0] → true.
  seed(cli2, {"abc12345"}, {makeFilterArg("abc12345", Lexer::Type::word)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, true,
       "detectPureUuidFilter: single 8-char hex prefix is pure UUID");

  // Single full 36-char UUID arg, FILTER-tagged, raw matches → true.
  seed(cli2, {"abc12345-1111-1111-1111-111111111111"},
       {makeFilterArg("abc12345-1111-1111-1111-111111111111", Lexer::Type::uuid)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, true,
       "detectPureUuidFilter: single full UUID is pure UUID");

  // Comma-set arg, FILTER-tagged, all elements present → true.
  seed(cli2, {"abc12345", "def67890"},
       {makeFilterArg("abc12345,def67890", Lexer::Type::set)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, true,
       "detectPureUuidFilter: comma-set of known prefixes is pure UUID");

  // UUID prefix + DOM `status` token (status:pending pair) → false.
  seed(cli2, {"abc12345"},
       {makeFilterArg("abc12345", Lexer::Type::word),
        makeFilterArg("status:pending", Lexer::Type::pair)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, false,
       "detectPureUuidFilter: uuid + status pair bails (DOM-attribute path)");

  // UUID prefix + virtual tag `+ACTIVE` (FILTER-tagged but raw not in uuid set,
  // and even if lex types matched, the raw wouldn't be in _uuid_list) → false.
  seed(cli2, {"abc12345"},
       {makeFilterArg("abc12345", Lexer::Type::word),
        makeFilterArg("+ACTIVE", Lexer::Type::tag)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, false,
       "detectPureUuidFilter: uuid + virtual tag bails (tag lex type)");

  // 8-char prefix shared by two real UUIDs would still pass the predicate —
  // resolution is TDB2::get's job, the predicate only inspects shape.
  // Hand-picked UUIDs are the only way to seed deterministic prefix collisions.
  seed(cli2, {"deadbeef"}, {makeFilterArg("deadbeef", Lexer::Type::word)});
  cli2.detectPureUuidFilter();
  t.is(cli2._pure_uuid_filter, true,
       "detectPureUuidFilter: shared-prefix uuid still pure (resolution deferred to get)");

  // Unit tests for looksLikeHexPrefix — guards detectPureUuidFilter's hex path.
  // Positive cases:
  t.ok(looksLikeHexPrefix("deadbeef"),
       "looksLikeHexPrefix: 8 lowercase hex chars");
  t.ok(looksLikeHexPrefix("DEADBEEF"),
       "looksLikeHexPrefix: 8 uppercase hex chars");
  t.ok(looksLikeHexPrefix("abc12345"),
       "looksLikeHexPrefix: 8 mixed-case hex chars");
  // Negative cases:
  t.ok(!looksLikeHexPrefix(""),
       "looksLikeHexPrefix: empty string rejected");
  t.ok(!looksLikeHexPrefix("abc"),
       "looksLikeHexPrefix: < 8 chars rejected");
  t.ok(!looksLikeHexPrefix("deadbeef1"),
       "looksLikeHexPrefix: > 8 chars rejected");
  t.ok(!looksLikeHexPrefix("deadbegg"),
       "looksLikeHexPrefix: non-hex char rejected");

  return 0;
}

////////////////////////////////////////////////////////////////////////////////
