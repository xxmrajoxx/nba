// Answers to the lesson 1 exercises.
// Run it: node learn/typescript/01-basic-answers.ts

// Copied from 01-basics.ts: each file has its own scope, so this file
// can't see the variables in the lesson file.
interface Player {
  name: string;
  team: string;
  points: number;
  assists: number;
  nickname?: string;
  rebounds: number;
}

const players: Player[] = [
  { name: "LeBron James", team: "LAL", points: 25, assists: 8, rebounds: 10 },
  { name: "Stephen Curry", team: "GSW", points: 27, assists: 6, nickname: "Chef Curry", rebounds: 5 },
  { name: "Nikola Jokic", team: "DEN", points: 26, assists: 9, rebounds: 12 },
];

const scores: number[] = [112, 98, 120];

// ---------------------------------------------------------------
// Exercise 1: print only the scores over 100
// ---------------------------------------------------------------
console.log("Exercise 1:");

for (const score of scores) {
  if (score > 100) {
    console.log(score);
  }
}
// Prints 112 and 120. No break: the loop has to check every score.

// ---------------------------------------------------------------
// Exercise 2: add rebounds to Player
// ---------------------------------------------------------------
// Done above: `rebounds: number;` in the interface, and a value for each player.

// ---------------------------------------------------------------
// Exercise 3: the player with the most points
// ---------------------------------------------------------------
console.log("Exercise 3:");

function topScorer(list: Player[]): Player {
  let best = list[0];               // start with the first player

  for (const p of list) {           // loop through the parameter, `list`
    if (p.points > best.points) {   // does this player beat the best so far?
      best = p;                     // then they're the new best
    }
  }

  return best;
}

console.log(topScorer(players).name);   // Stephen Curry

// Step by step:
//   best = LeBron (25)
//   LeBron: 25 > 25? no
//   Curry:  27 > 25? yes, best = Curry
//   Jokic:  26 > 27? no
//   return Curry
