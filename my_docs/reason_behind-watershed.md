This is actually the key idea behind the entire algorithm, and it's not obvious at first because **Flow Direction** and **Watershed** were originally designed for hydrology, not trees.

Let's break it down.

---

# First, what is your CHM?

A **Canopy Height Model (CHM)** is simply a raster where:

```
Pixel
10.5 m
11.2 m
15.8 m
18.3 m
23.4 m
...
```

Each pixel stores the height of the canopy.

Imagine one tree:

```
          27
       25 26 24
    22 24 25 23
 18 20 21 20 18
14 15 16 15 14
```

This is literally a hill.

The tallest point is the treetop.

The edges are lower.

---

# The problem

Suppose two trees touch.

Your CHM becomes

```
      26            24
   25 26 24      23 24 22
22 24 25 23 20 22 23 21
18 20 21 20 18 19 20 18
```

Now all pixels are connected.

You want to know

> Which pixels belong to Tree A?

and

> Which belong to Tree B?

The CHM itself doesn't tell you.

It only stores heights.

---

# Watershed solves this

Hydrology normally looks like this.

Mountain

```
      ^
     / \
    /   \
___/     \____
```

Rain falls.

Every raindrop flows downhill.

All water flowing to one river belongs to one watershed.

---

We reverse the idea.

Instead of mountains...

We make trees into valleys.

---

# Why invert?

Original CHM

```
      28
   24 26 23
20 21 22 20
15 16 17 16
```

Invert it

```
6
8 7 9
12 11 10
17 16 15
```

Now the treetop is the LOWEST point.

Everything slopes toward it.

---

# Flow Direction

Flow Direction asks

> If I pour water on this pixel...

Which neighboring pixel does it flow into?

Example

```
18 16 14
17 12 10
19 13  5
```

Water goes

```
18 →
16 →
14 ↓

17 →
12 →
10 ↓

19 →
13 →
5
```

Eventually every pixel reaches the lowest point.

---

# Watershed

Now place one seed at every detected treetop.

Each surrounding pixel follows the flow direction.

Eventually every pixel ends at exactly one seed.

That creates

```
AAAAAAAAAAAA

AAAAAAAABBBB

AAAAAAABBBBB

BBBBBBBBBBBB
```

Each letter is one crown.

---

# Why not just use Local Maxima?

Local maxima only finds

```
•
      •
          •
```

Those are treetops.

It does **not** tell you

```
###########
####Tree####
###########
```

the crown boundary.

---

# Why not threshold heights?

Suppose

```
Tree A touches Tree B
```

Thresholding gives

```
###############
###############
###############
```

One giant blob.

No separation.

---

# Watershed splits touching crowns

Suppose

```
        ▲          ▲
      Tree A    Tree B
```

Thresholding

```
####################
####################
```

Watershed

```
AAAAAAAAABBBBBBBBBB
AAAAAAAAABBBBBBBBBB
AAAAAAAAABBBBBBBBBB
```

Now each polygon represents one tree.

---

# Why is this method popular?

Because it's simple, fast, and works surprisingly well on CHMs.

It's one of the standard approaches in forestry and urban tree mapping:

1. Detect treetops (Local Maxima).
2. Invert the CHM.
3. Compute Flow Direction.
4. Run Watershed.
5. Convert watershed regions to crown polygons.

Many GIS and remote sensing tools implement some variation of this workflow.
