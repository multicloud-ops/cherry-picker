# cherry-picker
Bot for cherry picking commits via pull request from the master branch to the release branch.

## What does a cherry picker bot do?

Typically the master has a collection of features.  Some in development and some being fixed.  By using the release cutter bot (see below), you can create a feature branch which is nothing more than a sample of the master branch code at a specific point in development.  Once the feature branch has been creaeted, development continues on the master branch.  At some point in time you may feel you want to add the newer features and bug fixes to the release branch you created.  The cherry-picker bot provides a way for you to do that.

Assuming your master branch has commits that look like this:

1 - 2 - 3 - 4 - 5 - 6 ...

The release branch you selected only contains:

1 - 2 - 3

If you want to add a new feature "6" that is critical to your release branch, the cherry-picker bot will allow that.  Your new release will look like this:

1 - 2 - 3 - 6


## How to activate this bot.

This bot is activated by adding two labels on to each pull request.  

The first label is "bug", this tells the cherry picker that a bug was fixed or something was added to the master branch that needs to be included in the release branch target.

The second label is the name of the release branch in a very special format.  Chaning this format will cause the cherry-pick to be ignored.  The format is "release/release-x.x".

You should have created your release using the release-cutter bot to add the required formatting to your release to be cherry-picked.  This bot can be found here: https://github.com/multicloud-ops/release-cutter

So a typical pull request intended for delivery to a release branch would go something like... decide what commit you want to include in the release branch.  Create a pull request with the labels "bug" and "release/release-2.2".  When this content is cherry picked you should see it create a pull request on the release branch you specified (release-2.2).  The owner of that release branch can decide to either merge that request into the release branch release or just cancel it.  The determination is made by the release team for that release.



