// Lesson 1: TypeScript basics for a Python programmer
//
// Run it:          node learn/typescript/01-basics.ts
// See type errors: open this file in VS Code (red squiggles)
//
// TypeScript is JavaScript plus types. Your editor (or the `tsc` compiler) checks
// the types, then they are thrown away: at run time it's plain JavaScript.

// ---------------------------------------------------------------
// 1. Your loops.py, in TypeScript
// ---------------------------------------------------------------
// Python:
//   numbers = [1, 2, 3, 4, 5, 6]
//   for number in numbers:
//       print(number)
//       if number == 3:
//           print("Found 3, stopping")
//           break

const numbers = [1, 2, 3, 4, 5, 6];

for (const number of numbers) {
  console.log(number);
  if (number === 3) {
    console.log("Found 3, stopping");
    break;
  }
}

// What changed:
// - `const` declares a variable that can't be reassigned. Use `let` if it will change.
// - Braces { } mark blocks instead of indentation. Semicolons end statements.
// - `for ... of` is Python's `for ... in`. JavaScript also has a `for ... in`, but
//   it loops over keys/indexes, not values, so avoid it for arrays.
// - Use `===` for equality, never `==` (it does surprising type conversions).
// - `console.log` is `print`.

// ---------------------------------------------------------------
// 2. Type annotations
// ---------------------------------------------------------------
// Hover over `numbers` above in VS Code: it shows `const numbers: number[]`.
// TypeScript worked out the type itself. You can also write types, like Python hints:

const teamName: string = "Lakers";
let wins: number = 0;          // one number type, no int/float split
const isHome: boolean = true;  // lowercase true/false
const scores: number[] = [112, 98, 120];

wins = wins + 1;

for (const score of scores) {     // go through 112, 98, 120 on at a time
  if (score > 100)  {             // only when the score is over 100..
    console.log(score);// print the score itself 
  } 
}

for (const score of scores) {
  if (score < 115) {
    console.log(score);
    break;
  }
}
// Unlike Python, these are enforced. Uncomment the next line and VS Code
// underlines it in red:
// wins = "ten";

console.log(teamName, wins, isHome, scores);

// ---------------------------------------------------------------
// 3. Objects and interfaces (like a dataclass or TypedDict)
// ---------------------------------------------------------------
interface Player {
  name: string;
  team: string;
  points: number;
  assists: number;
  nickname?: string;  // `?` = optional, may be undefined (Python's None)
  rebounds: number; 
}

const players: Player[] = [
  { name: "LeBron James", team: "LAL", points: 25, assists: 8, rebounds: 10 },
  { name: "Stephen Curry", team: "GSW", points: 27, assists: 6, nickname: "Chef Curry", rebounds: 5 },
  { name: "Nikola Jokic", team: "DEN", points: 26, assists: 9, rebounds: 12 },
];

// Try: misspell a field (`pionts: 25`) or leave one out. TypeScript flags it.

// ---------------------------------------------------------------
// 4. Functions
// ---------------------------------------------------------------
// Python: def total_contributions(p: Player) -> int:
function totalContributions(p: Player): number {
  return p.points + p.assists * 2;
}



// Arrow functions are like Python's lambda, but can span several lines.
// Backtick strings with ${...} are Python's f-strings.
const describe = (p: Player): string => `${p.name} (${p.team}): ${p.points} pts`;

for (const p of players) {
  console.log(describe(p), "| contributions:", totalContributions(p));
}

// ---------------------------------------------------------------
// 5. List-comprehension equivalents
// ---------------------------------------------------------------
// Python: [p.name for p in players if p.points > 25]
const highScorers = players.filter((p) => p.points > 25).map((p) => p.name);
console.log("Over 25 ppg:", highScorers);

// Python: sum(p.points for p in players)
const totalPoints = players.reduce((sum, p) => sum + p.points, 0);
console.log("Total points:", totalPoints);

// ---------------------------------------------------------------
// 6. Optional values
// ---------------------------------------------------------------
for (const p of players) {
  // p.nickname has type `string | undefined`. `??` gives a fallback when it's
  // undefined, like Python's `p.nickname if p.nickname is not None else p.name`.
  console.log(p.nickname ?? p.name);
}

// Try adding `console.log(p.nickname.toUpperCase());` inside that loop.
// TypeScript warns that nickname might be undefined. In Python you'd only
// find out when the program crashed.

// ---------------------------------------------------------------
// Exercises: write your answers below, run the file, and fix any red squiggles
// ---------------------------------------------------------------
// 1. Loop over `scores` and print only the ones over 100.
// 2. Add a `rebounds: number` field to the Player interface, then fix the
//    errors that appear.
// 3. Write `function topScorer(list: Player[]): Player` that returns the
//    player with the most points.