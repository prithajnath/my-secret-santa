describe("User Sign In", () => {
  beforeAll(async () => {
    await page.goto("http://secret-santa-web:9000/login");
  });

  it("User can sign in and edit their profile", async () => {
    await page.evaluate(async () => {
      const username = document.querySelector("#username");
      username.value = "helenkeller";

      const password = document.querySelector("#password");
      password.value = "helloworld";

      const signInButton = document.querySelector("button.santa-button");
      await signInButton.click();
    });

    await page.waitForNavigation();

    const new_hint = "I like Rick and Morty stuff";
    const new_address =
      "99281 Zimmerman Manor Suite 425, East Hannah, SC 45121";

    await page.evaluate(async () => {
      const editButton = [
        ...document.querySelectorAll("button.santa-button"),
      ].find((x) => x.innerText === "Edit");

      await editButton.click();
    });

    await page.waitForNavigation();

    await page.evaluate(async (new_hint, new_address) => {
      const hint = document.querySelector("#hint");
      hint.value = "I like Rick and Morty stuff";

      const address = document.querySelector("#address");
      address.value = "99281 Zimmerman Manor Suite 425, East Hannah, SC 45121";

      const saveButton = [
        ...document.querySelectorAll("button.santa-button"),
      ].find((x) => x.innerText === "Save");

      await saveButton.click();
    });

    await page.waitForNavigation();

    await expect(
      page.evaluate(async () => {
        const allInnerText = [
          ...document.querySelector("h2").parentElement.children,
        ].map((x) => x.innerText);
        const HintIndex = allInnerText.indexOf("Hint");
        return allInnerText[HintIndex + 1];
      })
    ).resolves.toMatch(new_hint);

    await expect(
      page.evaluate(async () => {
        const allInnerText = [
          ...document.querySelector("h2").parentElement.children,
        ].map((x) => x.innerText);
        const AddressIndex = allInnerText.indexOf("Address");
        return allInnerText[AddressIndex + 1];
      })
    ).resolves.toMatch(new_address);
  });
});
